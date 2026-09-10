"""Deterministic fixed-depth search output, for diffing one build against another.

Exists because `tests/test_search_equivalence.py` cannot test the numba search: it hooks
`SearchContext.check_time`, `TimeUp` and `tt.clear()`, which are all `search.py` concepts.
`nsearch.py` has none of them, so the only equivalence harness in the repo covers the
Python fallback -- the path that has not played a rated game since v10.

The point of this tool is exactness. PVS is an exact optimisation: null-window searching
with a correct re-search must return the *same best move and the same score* as a plain
full-window search, in fewer nodes. Any change in the result means the re-search logic is
wrong, and no game-based test will tell you that -- it will just quietly play worse.

Run once per build and diff:

    python tools/fixed_depth_probe.py --snapshot snapshots/v11 --depth 7 > a.txt
    python tools/fixed_depth_probe.py --depth 7 > b.txt
    diff a.txt b.txt

Time is deliberately removed as a variable: `time_left_ms` is enormous and `max_depth`
bounds the search, so the result depends only on the search logic.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import chess
import numpy as np

REPO = Path(__file__).resolve().parent.parent

# A budget large enough that the deadline is never the thing that stops the search.
HUGE_CLOCK_MS = 3_600_000

POSITIONS = [
    ("opening", "r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8"),
    ("middlegame", "r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6"),
    ("sharp", "r2q1rk1/pp1bbppp/2np1n2/4p3/2B1P3/2NP1N2/PPPB1PPP/R2Q1RK1 w - - 4 10"),
    ("endgame", "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"),
    ("krk", "4R3/8/8/3k1K2/8/8/8/8 w - - 15 83"),
    # tactical positions carried over from tests/test_search_equivalence.py
    ("tactical-1", "r1b1k2r/pppp1ppp/2n2n2/4p3/1bB1P2q/2N2Q2/PPPP1PPP/R1B1K1NR w KQkq - 4 5"),
    ("tactical-2", "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"),
    ("tactical-3", "3r1rk1/1pp2ppp/p1q2b2/4p3/4P1b1/2P2N2/PP1N1PPP/R2QR1K1 w - - 0 14"),
    ("tactical-4", "r1bqk2r/ppp2ppp/2n5/3pP3/1b1P4/5N2/PP1B1PPP/R2QKB1R b KQkq - 2 9"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=None,
                        help="engine directory to load instead of the working tree")
    parser.add_argument("--depth", type=int, default=7)
    args = parser.parse_args()

    root = args.snapshot.resolve() if args.snapshot else REPO
    sys.path.insert(0, str(root))
    import nsearch  # noqa: PLC0415
    from bitboard import from_chess_board  # noqa: PLC0415

    empty_keys = np.array([], dtype=np.uint64)
    empty_vals = np.array([], dtype=np.int32)

    def search(fen: str) -> tuple[str, float, int, int]:
        nsearch.clear_tt()
        pieces, colors, state = from_chess_board(chess.Board(fen))
        move, score, nodes, depth = nsearch.numba_search(
            pieces, colors, state, HUGE_CLOCK_MS, empty_keys, empty_vals, 0,
            __import__("time").time(),
            nsearch.tt_keys, nsearch.tt_depths, nsearch.tt_scores,
            nsearch.tt_flags, nsearch.tt_moves, args.depth,
        )
        from bitboard import decode_move  # noqa: PLC0415
        return decode_move(move), float(score), int(nodes), int(depth)

    search(chess.STARTING_FEN)  # warm the JIT

    print(f"# engine: {root}")
    print(f"# max_depth={args.depth}  time_left_ms={HUGE_CLOCK_MS} (time is not a factor)")
    print(f"# {'position':<13}{'move':>7}{'score':>10}{'depth':>7}{'nodes':>14}")
    total = 0
    for name, fen in POSITIONS:
        move, score, nodes, depth = search(fen)
        total += nodes
        # nodes deliberately excluded from the diff-critical columns: PVS must not change
        # move or score, but is expected to change (reduce) nodes.
        print(f"{name:<15}{move:>7}{score:>10.1f}{depth:>7}   | nodes {nodes:,}")
    print(f"# total nodes {total:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
