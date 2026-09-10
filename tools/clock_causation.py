"""Does more thinking time actually make OUR engine play better moves?

The CPL analysis in runs/2026-09-10-v12/FINDINGS-cpl.md found that slow moves blunder
6.7x MORE than fast ones, and that moves which blew their budget by 2-13x had below
average CPL. But that is correlational and confounded: the engine spends longer on hard
positions, so time spent is a proxy for difficulty, not a cause of accuracy.

This is the controlled version. Same position, several fixed budgets, measure the
centipawn loss of the move chosen at each. Position difficulty is held constant by
construction, so any trend is causal.

It decides whether a time-management model is worth building at all:
  CPL falls with time  -> thinking longer helps; deciding WHERE to spend it is worth Elo
  CPL flat with time   -> the 30.9s we leave unspent is not costing us anything

    python tools/clock_causation.py --positions 40
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import statistics
import sys
from pathlib import Path

import chess
import chess.engine
import chess.pgn

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

LOGDIRS = [Path.home() / "Desktop/AIChessHackathon/v11-game-logs",
           Path.home() / "Desktop/AIChessHackathon/v10-game-logs"]
BUDGETS_MS = [200, 500, 1000, 2000, 5000, 10000]
CLAMP_CP = 1000.0


def our_positions(limit: int) -> list[tuple[str, chess.Board]]:
    """Positions from our own rated games where it was our turn to move."""
    out: list[tuple[str, chess.Board]] = []
    seen: set[str] = set()
    for d in LOGDIRS:
        for logp in sorted(d.glob("*.log")):
            text = logp.read_text()
            rnd = re.search(r"Round\s+Rated (\d+)", text).group(1)
            if rnd in seen:
                continue
            seen.add(rnd)
            pgnp = logp.with_suffix(".pgn")
            if not pgnp.exists():
                continue
            colour = re.search(r"Colour\s+(\w+)", text).group(1)
            pov = chess.WHITE if colour == "White" else chess.BLACK
            with open(pgnp) as fh:
                game = chess.pgn.read_game(fh)
            board = game.board()
            for i, mv in enumerate(game.mainline_moves()):
                # sample middlegame positions on our turn; skip the book-ish first moves
                if board.turn == pov and 8 <= i <= 60 and i % 7 == 0:
                    out.append((f"r{rnd}#{i}", board.copy()))
                board.push(mv)
    return out[:limit]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--positions", type=int, default=40)
    ap.add_argument("--depth", type=int, default=14)
    ap.add_argument("--engine", default="/opt/homebrew/bin/stockfish")
    ap.add_argument("--out", type=Path, default=Path("runs/2026-09-10-v12/clock_causation.json"))
    args = ap.parse_args()

    import nsearch  # noqa: PLC0415

    positions = our_positions(args.positions)
    print(f"{len(positions)} positions from our own rated games, "
          f"budgets {BUDGETS_MS} ms, scored at Stockfish depth {args.depth}\n")

    sf = chess.engine.SimpleEngine.popen_uci(args.engine)
    sf.configure({"Threads": 1, "Hash": 128})

    def cp(board: chess.Board, pov: chess.Color) -> float:
        s = sf.analyse(board, chess.engine.Limit(depth=args.depth))["score"].pov(pov)
        v = s.score(mate_score=100000)
        return max(-CLAMP_CP, min(CLAMP_CP, float(v)))

    nsearch.clear_tt()
    nsearch.get_move_with_info(chess.Board(), 2000, {})     # warm the JIT

    rows: list[dict] = []
    for tag, board in positions:
        pov = board.turn
        best = cp(board, pov)
        for ms in BUDGETS_MS:
            nsearch.clear_tt()          # each budget starts cold, or later runs cheat
            uci, _, _ = nsearch.get_move_with_info(board.copy(), ms, {})
            board.push(chess.Move.from_uci(uci))
            after = cp(board, pov)
            board.pop()
            rows.append({"tag": tag, "budget_ms": ms, "cpl": max(0.0, best - after), "move": uci})
        print(f"  {tag:<12} " + "  ".join(
            f"{ms//1000 if ms>=1000 else ms}{'s' if ms>=1000 else 'ms'}:"
            f"{[r for r in rows if r['tag']==tag and r['budget_ms']==ms][0]['cpl']:>5.0f}"
            for ms in BUDGETS_MS), flush=True)

    sf.quit()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=1))

    print(f"\n=== centipawn loss by budget, same positions throughout ===")
    print(f"{'budget':>9}{'mean CPL':>11}{'median':>9}{'>=100cp':>10}")
    means = []
    for ms in BUDGETS_MS:
        c = [r["cpl"] for r in rows if r["budget_ms"] == ms]
        big = sum(1 for x in c if x >= 100)
        means.append(statistics.mean(c))
        print(f"{ms:>7}ms{statistics.mean(c):>11.1f}{statistics.median(c):>9.1f}"
              f"{big:>7} ({big/len(c):.0%})")

    lo, hi = means[0], means[-1]
    print(f"\n  200ms -> {BUDGETS_MS[-1]}ms: mean CPL {lo:.1f} -> {hi:.1f} "
          f"({(hi-lo)/lo*100:+.0f}%)")
    if hi < lo * 0.8:
        print("  VERDICT: more time causes materially better moves. A time-management")
        print("  model that decides WHERE to spend is worth building.")
    elif hi > lo * 1.2:
        print("  VERDICT: more time makes things WORSE. Investigate before trusting this.")
    else:
        print("  VERDICT: flat. Thinking longer does not buy accuracy in this engine,")
        print("  so the 30.9s we leave unspent is not what is costing us. Spend the")
        print("  effort on evaluation instead.")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
