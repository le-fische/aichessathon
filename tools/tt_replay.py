"""Nodes-to-fixed-depth with a WARM transposition table, replayed over real games.

Why this tool exists
--------------------
`tools/bench_v11.py` calls `nsearch.clear_tt()` before every position, so its searches
touch 3.7-7.0% of the 16.7M-entry table. Any question about *replacement policy* is
therefore invisible to it: with a table that empty, nothing is ever evicted and
always-replace and depth-preferred behave identically. Measuring a TT change with
bench_v11 would show ~zero difference and wrongly bin the change.

This tool keeps the table warm the way a real game does. It replays our own rated PGNs
move by move without ever clearing the table, and at sampled plies runs a **fixed-depth**
search, recording nodes, effective branching factor and table occupancy.

Two properties make it a good instrument:

* **Paired.** Both policies see the identical position at the identical ply with a table
  filled by the identical preceding moves. The comparison is move-for-move, so it has far
  less variance than playing games -- a node-level change needs a node-level measurement.
* **Time is not a variable.** `max_depth` bounds the search and the clock is enormous, so
  the result depends only on search logic and on what the table managed to keep.

The primary readout is **nodes to reach a fixed depth**. That is the thing a replacement
policy is supposed to improve: a table that keeps the good deep entries should find the
same depth for fewer nodes.

Usage
-----
    CHESSATHON_REQUIRE_NUMBA=1 python tools/tt_replay.py \
        --snapshot snapshots/tt-always --depth 10 --out runs/.../tt-always.csv

    CHESSATHON_REQUIRE_NUMBA=1 python tools/tt_replay.py \
        --snapshot snapshots/tt-depth  --depth 10 --out runs/.../tt-depth.csv

PGNs are replayed back to back with the table never cleared, so the ply axis is
cumulative and reaches the ply 100 / 200 / 300 checkpoints even though a single rated
game only runs ~100-120 plies. Real games clear the table between games, so treat high
cumulative plies as a deliberate stress of the eviction path rather than as a faithful
model of one game.

One run at a time. Concurrent CPU load invalidates the node rate, though not the node
counts themselves.
"""

from __future__ import annotations

import argparse
import csv
import glob
import math
import os
import sys
import time
from pathlib import Path

import chess
import chess.pgn

REPO = Path(__file__).resolve().parent.parent

# Large enough that the deadline never stops the search: max_depth is the only bound.
HUGE_CLOCK_MS = 3_600_000


def tt_occupancy(nsearch) -> float:
    """Percent of transposition table slots holding an entry.

    Mirrors tools/longgame.py:tt_occupancy so the two tools report the same number.
    """
    return float((nsearch.tt_keys != 0).sum()) / float(nsearch.TT_SIZE) * 100.0


def default_pgns() -> list[str]:
    """Rated PGNs, longest first, so the early plies come from real long games."""
    base = REPO.parent
    paths = sorted(glob.glob(str(base / "v1*-game-logs" / "*.pgn")))
    scored = []
    for p in paths:
        with open(p) as fh:
            game = chess.pgn.read_game(fh)
        if game is None:
            continue
        scored.append((sum(1 for _ in game.mainline_moves()), p))
    scored.sort(reverse=True)
    return [p for _, p in scored]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True,
                        help="engine directory to load instead of the working tree")
    parser.add_argument("--depth", type=int, default=10, help="fixed search depth")
    parser.add_argument("--every", type=int, default=10, help="sample every N plies")
    parser.add_argument("--max-ply", type=int, default=400, help="stop after this many plies")
    parser.add_argument("--pgn", action="append", default=None, help="PGN to replay (repeatable)")
    parser.add_argument("--out", type=Path, default=None, help="write per-sample CSV here")
    args = parser.parse_args()

    if os.environ.get("CHESSATHON_REQUIRE_NUMBA") != "1":
        print("WARNING: CHESSATHON_REQUIRE_NUMBA is not 1; a silent fallback to the "
              "Python search would measure the wrong engine.", flush=True)

    sys.path.insert(0, str(args.snapshot.resolve()))
    import nsearch  # noqa: PLC0415

    pgns = args.pgn if args.pgn else default_pgns()
    if not pgns:
        raise SystemExit("no PGNs found to replay")

    nsearch.clear_tt()
    print(f"engine   {args.snapshot}")
    print(f"depth    {args.depth} fixed, clock {HUGE_CLOCK_MS} ms (time is not a factor)")
    print(f"sampling every {args.every} plies, table NEVER cleared\n")
    print(f"{'ply':>5}{'depth':>7}{'nodes':>12}{'EBF':>7}{'occ%':>9}{'sec':>7}  position")

    rows: list[dict] = []
    ply = 0
    for path in pgns:
        with open(path) as fh:
            game = chess.pgn.read_game(fh)
        if game is None:
            continue
        board = game.board()
        for move in game.mainline_moves():
            # Search EVERY ply. In a real game every move runs a search, and it is those
            # searches that fill the table -- sampling only every Nth ply would fill it N
            # times slower than reality and understate the eviction pressure the
            # replacement policy exists to handle. Recording is sampled; searching is not.
            if not board.is_game_over():
                started = time.time()
                # position_counts empty: repetition detection is not what is being measured
                _, _, nodes = nsearch.get_move_with_info(
                    board, HUGE_CLOCK_MS, {}, args.depth)
                elapsed = time.time() - started
                occ = tt_occupancy(nsearch)
                nodes = int(nodes)
                # nodes == 0 means the root Syzygy probe answered without searching;
                # there is no tree to measure, so the sample carries no information.
                if ply % args.every == 0:
                    if nodes > 0:
                        ebf = nodes ** (1.0 / args.depth)
                        rows.append({"ply": ply, "depth": args.depth, "nodes": nodes,
                                     "ebf": round(ebf, 4), "occupancy_pct": round(occ, 4),
                                     "sec": round(elapsed, 3), "fen": board.fen()})
                        print(f"{ply:>5}{args.depth:>7}{nodes:>12,}{ebf:>7.2f}{occ:>9.3f}"
                              f"{elapsed:>7.2f}  {board.fen()[:40]}", flush=True)
                    else:
                        print(f"{ply:>5}{args.depth:>7}{'tablebase':>12}{'':>7}{occ:>9.3f}"
                              f"{elapsed:>7.2f}  (root probe answered, no tree)", flush=True)
            board.push(move)
            ply += 1
            if ply >= args.max_ply:
                break
        if ply >= args.max_ply:
            break

    if not rows:
        print("\nno measurable samples")
        return 1

    total_nodes = sum(r["nodes"] for r in rows)
    mean_ebf = sum(r["ebf"] for r in rows) / len(rows)
    print(f"\n{len(rows)} samples at fixed depth {args.depth}")
    print(f"total nodes      {total_nodes:,}")
    print(f"mean nodes       {total_nodes / len(rows):,.0f}")
    print(f"mean EBF         {mean_ebf:.3f}")
    print(f"final occupancy  {rows[-1]['occupancy_pct']:.3f}%")

    # The checkpoints Le asked for.
    print("\ncheckpoints:")
    for target in (100, 200, 300):
        near = min(rows, key=lambda r: abs(r["ply"] - target))
        if abs(near["ply"] - target) <= args.every:
            print(f"  ply {near['ply']:>3}  nodes {near['nodes']:>11,}  "
                  f"EBF {near['ebf']:.2f}  occupancy {near['occupancy_pct']:.3f}%")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
