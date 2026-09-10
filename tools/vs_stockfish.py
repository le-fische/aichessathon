"""Play the agent against Stockfish at a capped Elo, at the tournament time control.

Every measurement on this project so far has been self-relative -- v10 against v9, numba
against Python, candidate against baseline. This is the absolute one: 2200 is the
top-50 benchmark.

Our side is called in-process exactly as the platform calls it, `get_move(fen,
time_left_ms)`, so what is measured is the thing that ships. Stockfish is driven over UCI
by python-chess. Do NOT route our side through tools/uci_wrapper.py: wrapping the agent
in UCI to face a UCI engine adds a process and a failure mode for nothing, and that
wrapper is broken anyway (it resolves agent.py against tools/).

Stockfish is a local sparring partner only. It is never shipped: the rules ban third
party engines *inside the submission*, and baselines/ is gitignored.

    CHESSATHON_REQUIRE_NUMBA=1 python tools/vs_stockfish.py --elo 2200 --games 40

One game at a time, never in parallel -- concurrent games on this Mac are the leading
suspect for previous local time-loss numbers.
"""

from __future__ import annotations

import argparse
import math
import os
import shutil
import sys
import time
from pathlib import Path

import chess
import chess.engine

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

BASE_MS = 120_000
INCREMENT_MS = 500

# The curated openings our rated games actually start from, taken from the PGN archive.
# Starting from the standard position would measure something the platform never asks for.
OPENINGS = [
    ("King's Indian", "r2qkb1r/1p3ppp/p1npbn2/4p1B1/4P3/N1N2P2/PPP3PP/R2QKB1R b KQkq - 3 9"),
    ("Nimzo-Indian", "rnbq1rk1/ppp2ppp/4pn2/8/1bBP4/2N1P2P/PP3PP1/R1BQK1NR b KQ - 0 7"),
    ("Dutch Stonewall", "rnbqk2r/ppp3pp/3bpn2/3p1p2/2PP4/5NP1/PP2PPBP/RNBQ1RK1 b kq - 0 6"),
    ("Sicilian Closed", "r1bq1rk1/pp2npbp/2np2p1/2p1p3/4P3/P1NP2PP/1PP1NPB1/R1BQK2R w KQ - 3 9"),
    ("Queen's Indian", "rn1q1rk1/pbp1bppp/1p1ppn2/8/2PP4/PP3NP1/4PPBP/RNBQ1RK1 b - - 0 8"),
    ("Reti", "rnbq1rk1/1pp2pbp/3p1np1/p2Pp3/2P1P3/2N2N1P/PP2BPP1/R1BQK2R b KQ - 0 8"),
]


def find_stockfish(explicit: str | None) -> str:
    for candidate in (explicit, os.environ.get("STOCKFISH"),
                      str(REPO / "baselines" / "stockfish" / "stockfish"),
                      shutil.which("stockfish")):
        if candidate and Path(candidate).exists():
            return candidate
    raise SystemExit(
        "Stockfish not found. Put it at baselines/stockfish/stockfish (gitignored, never\n"
        "shipped), or pass --engine PATH, or set STOCKFISH."
    )


def elo_from_score(score: float, games: int) -> tuple[float, float]:
    """Elo difference implied by a score, and the standard error in Elo."""
    if games == 0:
        return 0.0, 0.0
    eps = 1.0 / (2 * games)
    clamped = min(max(score, eps), 1 - eps)
    elo = 400.0 * math.log10(clamped / (1 - clamped))
    se_score = math.sqrt(max(score * (1 - score), eps) / games)
    # derivative of the logistic at `clamped`, for a first-order error bar
    slope = 400.0 / (math.log(10) * clamped * (1 - clamped))
    return elo, slope * se_score


def play_game(engine: chess.engine.SimpleEngine, get_move, board: chess.Board,
              agent_is_white: bool, ply_cap: int) -> tuple[str, str, float, int]:
    """Returns (result_for_agent, termination, agent_clock_left_s, plies)."""
    clocks = {chess.WHITE: float(BASE_MS), chess.BLACK: float(BASE_MS)}
    agent_colour = chess.WHITE if agent_is_white else chess.BLACK
    plies = 0

    while plies < ply_cap:
        if board.is_game_over(claim_draw=True):
            break
        turn = board.turn
        if turn == agent_colour:
            started = time.time()
            try:
                uci = get_move(board.fen(), int(clocks[turn]))
            except Exception as exc:  # a crash is a loss, exactly as on the platform
                return ("loss", f"crash: {type(exc).__name__}: {exc}", clocks[agent_colour] / 1000, plies)
            spent = (time.time() - started) * 1000
            clocks[turn] -= spent
            if clocks[turn] < 0:
                return ("loss", "flag", clocks[agent_colour] / 1000, plies)
            try:
                move = chess.Move.from_uci(uci)
            except Exception:
                return ("loss", f"malformed move {uci!r}", clocks[agent_colour] / 1000, plies)
            if move not in board.legal_moves:
                return ("loss", f"illegal move {uci}", clocks[agent_colour] / 1000, plies)
        else:
            limit = chess.engine.Limit(
                white_clock=clocks[chess.WHITE] / 1000, black_clock=clocks[chess.BLACK] / 1000,
                white_inc=INCREMENT_MS / 1000, black_inc=INCREMENT_MS / 1000,
            )
            started = time.time()
            move = engine.play(board, limit).move
            clocks[turn] -= (time.time() - started) * 1000
            if move is None:
                return ("win", "opponent resigned", clocks[agent_colour] / 1000, plies)
        board.push(move)
        clocks[turn] += INCREMENT_MS
        plies += 1

    outcome = board.outcome(claim_draw=True)
    left = clocks[agent_colour] / 1000
    if outcome is None:
        return ("draw", "ply cap", left, plies)
    if outcome.winner is None:
        return ("draw", outcome.termination.name.lower(), left, plies)
    won = (outcome.winner == agent_colour)
    return ("win" if won else "loss", outcome.termination.name.lower(), left, plies)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elo", type=int, default=2200)
    parser.add_argument("--games", type=int, default=40)
    parser.add_argument("--engine", default=None)
    parser.add_argument("--ply-cap", type=int, default=600)
    parser.add_argument("--threads", type=int, default=1)
    args = parser.parse_args()

    if os.environ.get("CHESSATHON_REQUIRE_NUMBA") != "1":
        print("WARNING: CHESSATHON_REQUIRE_NUMBA is not 1; a silent fallback to the "
              "Python search would measure the wrong engine.", flush=True)

    binary = find_stockfish(args.engine)
    from agent import get_move  # imported after the warning so JIT cost is visible

    engine = chess.engine.SimpleEngine.popen_uci(binary)
    engine.configure({"UCI_LimitStrength": True, "UCI_Elo": args.elo, "Threads": args.threads})

    print(f"agent vs Stockfish  UCI_Elo={args.elo}  threads={args.threads}")
    print(f"engine: {binary}")
    print(f"{BASE_MS/1000:.0f}s + {INCREMENT_MS/1000:.1f}s, {args.games} games, "
          f"colours alternating, ply cap {args.ply_cap}\n", flush=True)

    wins = draws = losses = 0
    terminations: dict[str, int] = {}
    try:
        for game in range(args.games):
            name, fen = OPENINGS[game % len(OPENINGS)]
            agent_is_white = (game % 2 == 0)
            board = chess.Board(fen)
            started = time.time()
            result, termination, left, plies = play_game(
                engine, get_move, board, agent_is_white, args.ply_cap)
            terminations[termination] = terminations.get(termination, 0) + 1
            if result == "win":
                wins += 1
            elif result == "draw":
                draws += 1
            else:
                losses += 1
            played = game + 1
            score = (wins + draws / 2) / played
            elo, err = elo_from_score(score, played)
            print(f"game {played:>3}/{args.games}  {'W' if agent_is_white else 'B'}  "
                  f"{name:<16} {result:<5} by {termination:<22} "
                  f"{plies:>3} plies  clock left {left:>6.1f}s  {time.time()-started:>5.0f}s  "
                  f"| +{wins} ={draws} -{losses}  {score:.1%}  Elo diff {elo:+.0f} +/- {err:.0f}",
                  flush=True)
    finally:
        engine.quit()

    played = wins + draws + losses
    score = (wins + draws / 2) / played if played else 0.0
    elo, err = elo_from_score(score, played)
    print(f"\n+{wins} ={draws} -{losses} over {played} games, score {score:.1%}")
    print(f"terminations: " + ", ".join(f"{k} {v}" for k, v in sorted(terminations.items())))
    print(f"Elo difference vs Stockfish {args.elo}: {elo:+.0f} +/- {err:.0f}")
    print(f"implied absolute strength: {args.elo + elo:.0f}")
    if any(t.startswith(("crash", "illegal", "malformed")) or t == "flag" for t in terminations):
        print("\nWARNING: at least one game ended in a way that loses on the platform.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
