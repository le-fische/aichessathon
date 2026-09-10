"""Centipawn loss per move, joined to the time spent on it.

Le's hypothesis: short thinking time correlates with blundering, and if the bad moves
cluster at low time we need clock logic rather than more evaluation.

Data is the v10 RATED game logs -- real games from the live build, with per-move times
and clock-remaining in the .log and the moves in the matching .pgn. Stockfish scores each
position at fixed depth; CPL is best-move eval minus played-move eval, from our side.

Sharper than the scatter plot alone, and the reason this is worth running:
  - CPL of moves played on the PANIC path (clock < 3s, v10 returns a depth-0 move)
  - CPL of the 95 moves that went OVER budget -- did thinking 13x longer buy accuracy?
  - CPL against clock remaining, independent of time spent

    python tools/cpl_analysis.py --depth 14
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import statistics
import sys
from pathlib import Path

import chess
import chess.engine
import chess.pgn

LOGS = Path.home() / "Desktop/AIChessHackathon/v10-game-logs"
INC_MS = 500.0


def budget_ms(clock_ms: float) -> float:
    """v10/v11 budget model, so 'over budget' means over what the engine allowed itself."""
    if clock_ms < 3000:
        return min(200.0, clock_ms * 0.1)
    return min(clock_ms * 0.045 + 400.0, clock_ms * 0.25)


def parse_log(path: Path) -> tuple[str, list[tuple[int, str, float, float]]]:
    text = path.read_text()
    colour = re.search(r"Colour\s+(\w+)", text).group(1)
    moves = []
    for line in text.split("MOVES")[1].splitlines():
        m = re.match(r"\s*(\d+)\s+(\S+)\s+([\d.]+) s\s+([\d.]+) s", line)
        if m:
            moves.append((int(m.group(1)), m.group(2), float(m.group(3)) * 1000,
                          float(m.group(4)) * 1000))
    return colour, moves


# Evaluations are clamped before differencing. Without this a single forced mate scores
# +/-100000 and one position produces a CPL near 98,000, which destroys every mean while
# leaving the medians untouched -- exactly what the first run of this script did. Clamping
# to +/-1000cp is the standard ACPL convention: past a rook up, "more winning" is not a
# meaningful gradient and the move that gets there is not a blunder.
CLAMP_CP = 1000.0


def score_cp(engine, board: chess.Board, depth: int, pov: chess.Color) -> float | None:
    info = engine.analyse(board, chess.engine.Limit(depth=depth))
    cp = info["score"].pov(pov).score(mate_score=100000)
    if cp is None:
        return None
    return max(-CLAMP_CP, min(CLAMP_CP, float(cp)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--depth", type=int, default=14)
    ap.add_argument("--engine", default="/opt/homebrew/bin/stockfish")
    ap.add_argument("--out", type=Path, default=Path("runs/2026-09-10-v12/cpl.json"))
    args = ap.parse_args()

    engine = chess.engine.SimpleEngine.popen_uci(args.engine)
    engine.configure({"Threads": 1, "Hash": 128})

    rows: list[dict] = []
    seen: set[str] = set()
    for logp in sorted(LOGS.glob("*.log")):
        rnd = re.search(r"Round\s+Rated (\d+)", logp.read_text()).group(1)
        if rnd in seen:
            continue          # round 90 is duplicated on disk
        seen.add(rnd)
        pgnp = logp.with_suffix(".pgn")
        if not pgnp.exists():
            continue
        colour, timed = parse_log(logp)
        pov = chess.WHITE if colour == "White" else chess.BLACK

        with open(pgnp) as fh:
            game = chess.pgn.read_game(fh)
        board = game.board()
        our_index = 0
        for mv in game.mainline_moves():
            if board.turn == pov:
                if our_index < len(timed):
                    no, san, used, after = timed[our_index]
                    before = after + used - INC_MS
                    b = budget_ms(before)
                    best = score_cp(engine, board, args.depth, pov)
                    board.push(mv)
                    played = score_cp(engine, board, args.depth, pov)
                    board.pop()
                    if best is not None and played is not None:
                        rows.append(dict(rnd=rnd, no=no, san=san, used_ms=used,
                                         clock_before_ms=before, budget_ms=b,
                                         ratio=used / b if b else 0.0,
                                         cpl=max(0.0, best - played)))
                    our_index += 1
            board.push(mv)
        print(f"  round {rnd}: {our_index} of our moves scored", flush=True)

    engine.quit()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=1))

    def summarise(name: str, sel: list[dict]) -> None:
        if not sel:
            print(f"  {name:<38} n=0")
            return
        c = [r["cpl"] for r in sel]
        big = sum(1 for x in c if x >= 100)
        print(f"  {name:<38} n={len(sel):<5} mean CPL {statistics.mean(c):>7.1f}  "
              f"median {statistics.median(c):>6.1f}  >=100cp {big:>3} ({big/len(sel):>5.1%})")

    print(f"\n=== centipawn loss, {len(rows)} of our moves across {len(seen)} rated games "
          f"(Stockfish depth {args.depth}) ===")
    summarise("ALL MOVES", rows)
    print()
    summarise("panic path (clock < 3s)", [r for r in rows if r["clock_before_ms"] < 3000])
    summarise("low clock (3-10s)", [r for r in rows if 3000 <= r["clock_before_ms"] < 10000])
    summarise("mid clock (10-30s)", [r for r in rows if 10000 <= r["clock_before_ms"] < 30000])
    summarise("high clock (>30s)", [r for r in rows if r["clock_before_ms"] >= 30000])
    print()
    summarise("OVER budget (ratio > 1)", [r for r in rows if r["ratio"] > 1.0])
    summarise("  of those, ratio > 2", [r for r in rows if r["ratio"] > 2.0])
    summarise("within budget (ratio <= 1)", [r for r in rows if r["ratio"] <= 1.0])
    print()
    summarise("fastest quartile by time used", sorted(rows, key=lambda r: r["used_ms"])[:len(rows)//4])
    summarise("slowest quartile by time used", sorted(rows, key=lambda r: -r["used_ms"])[:len(rows)//4])
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
