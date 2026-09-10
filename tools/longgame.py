"""Long-game clock stress test: drive agent.get_move past clocksim.py's 84-ply cutoff.

clocksim.py imports `search` directly (never the numba path that ships), starts from
the standard position, stops when the self-play game ends, and clears the TT every
move. So it has never observed the shipping engine's clock past ply 84, has never
observed TT or counter growth, and has never observed the fallback handoff.

This drives the real contract -- agent.get_move(fen, time_left_ms) -- move after move
with the platform clock model copied from harness/referee.py (120 s base, 0.5 s
increment credited AFTER the move, flag when the clock goes below zero), out to the
600-ply draw cap.

Two independent agent module instances are loaded, one per colour, so each side keeps
its own game_board and its own position_counts, exactly as two containers would.
nsearch/search (and therefore the transposition table) are shared between them; that
makes the TT fill faster than in a real game, which is the conservative direction for
the growth question.

Phases:
  game   full-length self-play game with the real clock
  small  direct probes at tiny time_left_ms values (the flag test)

Env:
  LG_PHASE     game | small | both        (default both)
  LG_PLIES     ply cap                    (default 600)
  LG_FEN       start position             (default round-14-rudra's curated opening)
  LG_CLAIM     1 to let the referee claim threefold/fifty-move draws (default 0)
  LG_SNAP      directory holding the frozen engine snapshot
  LG_OUT       directory for the CSV trajectory
"""

from __future__ import annotations

import collections
import contextlib
import hashlib
import importlib.util
import io
import os
import re
import resource
import subprocess
import sys
import time
import types

SNAP = os.environ.get(
    "LG_SNAP",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "scratch", "longgame-snap"),
)
OUT = os.environ.get(
    "LG_OUT",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runs", "2026-09-09-longgame"),
)
PHASE = os.environ.get("LG_PHASE", "both")
PLY_CAP = int(os.environ.get("LG_PLIES", "600"))
CLAIM = os.environ.get("LG_CLAIM", "0") == "1"

# round-14-rudra: the curated opening of our longest real rated game (282 plies).
DEFAULT_FEN = "r2qkb1r/1p3ppp/p1npbn2/4p1B1/4P3/N1N2P2/PPP3PP/R2QKB1R b KQkq - 3 9"
FEN = os.environ.get("LG_FEN", DEFAULT_FEN)

BASE_MS = 120_000.0
INCREMENT_MS = 500.0

os.environ.setdefault("CHESSATHON_DEPTH_LOG", "1")

# cwd must be the snapshot dir: search.py opens the syzygy tablebase at the relative
# path "weights".
os.chdir(SNAP)
sys.path.insert(0, SNAP)

import chess  # noqa: E402

DEPTH_RE = re.compile(r"info depth (\d+) score cp (-?\d+) nodes (\d+)")


def sha256(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def load_agent(alias: str) -> types.ModuleType:
    """Load agent.py from the snapshot as an independent module instance."""
    spec = importlib.util.spec_from_file_location(alias, os.path.join(SNAP, "agent.py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


def numba_budget_ms(time_left_ms: float) -> tuple[float, bool]:
    """The budget nsearch.numba_search computes. Copied, not imported: the value is
    local to an njit function and cannot be read from outside."""
    if time_left_ms < 3000:
        return min(200.0, time_left_ms * 0.1), True
    return min(time_left_ms * 0.045 + 400.0, time_left_ms * 0.25), False


def python_budget_ms(time_left_ms: float) -> tuple[float, bool]:
    """The budget search.get_move computes."""
    if time_left_ms < 3000:
        return min(200.0, time_left_ms * 0.1), True
    budget = min(time_left_ms * 0.050 + 400.0, time_left_ms * 0.25)
    return min(budget + INCREMENT_MS * 0.8, time_left_ms * 0.25), False


def rss_mb() -> float:
    out = subprocess.run(
        ["ps", "-o", "rss=", "-p", str(os.getpid())], capture_output=True, text=True
    )
    try:
        return int(out.stdout.strip()) / 1024.0
    except ValueError:
        return -1.0


def peak_rss_mb() -> float:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # bytes on Darwin, kibibytes on Linux
    return raw / (1024.0 * 1024.0) if sys.platform == "darwin" else raw / 1024.0


def tt_occupancy(nsearch: types.ModuleType) -> float:
    import numpy as np

    return float((nsearch.tt_keys != 0).sum()) / float(nsearch.TT_SIZE) * 100.0


def timed_move(mod: types.ModuleType, fen: str, clock_ms: int) -> tuple[str, float, int, int, str]:
    """Call get_move, charge wall time, and harvest the depth log off stderr."""
    buf = io.StringIO()
    t0 = time.monotonic()
    with contextlib.redirect_stderr(buf):
        uci = mod.get_move(fen, clock_ms)
    used = (time.monotonic() - t0) * 1000.0
    err = buf.getvalue()
    match = DEPTH_RE.search(err)
    depth, nodes = (int(match.group(1)), int(match.group(3))) if match else (-1, -1)
    return uci, used, depth, nodes, err


def run_game(white: types.ModuleType, black: types.ModuleType, nsearch: types.ModuleType) -> None:
    board = chess.Board(FEN)
    mods = {chess.WHITE: white, chess.BLACK: black}
    clock = {chess.WHITE: BASE_MS, chess.BLACK: BASE_MS}
    budget_fn = numba_budget_ms if white.USE_NUMBA_SEARCH else python_budget_ms

    rows: list[tuple] = []
    worst = (0.0, 0, "", 0.0, 0.0)  # ratio, ply, fen, used, budget
    min_clock = {chess.WHITE: BASE_MS, chess.BLACK: BASE_MS}
    ended = "ply_cap"
    fell_back = False
    peak_rss = 0.0
    referee_would_stop: tuple[int, str] | None = None

    print(f"start fen : {FEN}")
    print(f"ply cap   : {PLY_CAP}   claim_draw={CLAIM}")
    print(f"numba     : white={white.USE_NUMBA_SEARCH} black={black.USE_NUMBA_SEARCH}")
    print()
    header = (
        f"{'ply':>4} {'mv':>4} {'side':<5} {'clock_in':>9} {'budget':>8} "
        f"{'used':>8} {'ratio':>6} {'clock_out':>10} {'d':>3} {'nodes':>9} "
        f"{'ttocc%':>7} {'rss':>7} {'cnt':>5}"
    )
    print(header)

    for ply in range(PLY_CAP):
        if referee_would_stop is None:
            ref = board.outcome(claim_draw=True)
            if ref is not None:
                referee_would_stop = (ply, ref.termination.name.lower())
                print(f"  -- the real referee would have stopped here: ply {ply} "
                      f"{ref.termination.name.lower()}; the clock instrument continues")
        if CLAIM:
            outcome = board.outcome(claim_draw=True)
            if outcome is not None:
                ended = outcome.termination.name.lower()
                break
        elif board.is_checkmate() or board.is_stalemate():
            ended = "checkmate" if board.is_checkmate() else "stalemate"
            break

        side = board.turn
        mod = mods[side]
        clock_in = clock[side]
        budget, panic = budget_fn(clock_in)

        uci, used, depth, nodes, err = timed_move(mod, board.fen(), int(clock_in))

        if "Falling back to Python search" in err or "Top-level get_move exception" in err:
            fell_back = True
            print(f"  !! ply {ply}: {err.strip().splitlines()[0]}")

        clock[side] -= used
        if clock[side] < min_clock[side]:
            min_clock[side] = clock[side]
        if clock[side] < 0:
            ended = f"FLAG ({'white' if side else 'black'})"
            rows.append((ply, board.fullmove_number, side, clock_in, budget, used, clock[side],
                         depth, nodes, board.fen()))
            break

        ratio = used / budget if budget > 0 else float("inf")
        if ratio > worst[0]:
            worst = (ratio, ply, board.fen(), used, budget)

        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            ended = f"ILLEGAL {uci} at ply {ply}"
            break

        occ = tt_occupancy(nsearch)
        rss = rss_mb()
        peak_rss = max(peak_rss, rss)
        counts = mod.position_counts_numba if mod.USE_NUMBA_SEARCH else mod.position_counts_py
        rows.append(
            (ply, board.fullmove_number, side, clock_in, budget, used, clock[side], depth, nodes,
             board.fen())
        )

        if ply < 12 or ply % 10 == 0 or clock[side] < 5000 or ratio > 1.0:
            print(
                f"{ply:>4} {board.fullmove_number:>4} {'white' if side else 'black':<5} "
                f"{clock_in/1000:>8.2f}s {budget:>7.0f}m {used:>7.0f}m {ratio:>6.2f} "
                f"{clock[side]/1000:>9.2f}s {depth:>3} {nodes:>9} {occ:>6.2f}% "
                f"{rss:>6.0f}M {len(counts):>5}"
            )

        board.push(move)
        clock[side] += INCREMENT_MS

    plies = len(rows)
    print()
    print(f"ended     : {ended}   plies={plies}   result={board.result(claim_draw=True)}")
    print(f"referee would have stopped at: {referee_would_stop}")
    print(f"fell back to python mid-game: {fell_back}")
    for side, name in ((chess.WHITE, "white"), (chess.BLACK, "black")):
        avail = BASE_MS + INCREMENT_MS * (plies / 2)
        print(
            f"  {name}: clock left {clock[side]/1000:7.2f}s   min clock {min_clock[side]/1000:7.2f}s   "
            f"used {(1 - clock[side]/avail)*100:5.1f}% of {avail/1000:.1f}s"
        )
    print(f"worst overshoot ratio: {worst[0]:.2f}x  at ply {worst[1]}  "
          f"used {worst[3]:.0f} ms against budget {worst[4]:.0f} ms")
    print(f"  fen: {worst[2]}")
    print(f"tt occupancy end: {tt_occupancy(nsearch):.2f}%   "
          f"white counter {len(white.position_counts_numba or white.position_counts_py)}   "
          f"black counter {len(black.position_counts_numba or black.position_counts_py)}")
    print(f"rss now {rss_mb():.0f} MB   peak rss {peak_rss:.0f} MB   "
          f"ru_maxrss {peak_rss_mb():.0f} MB   (limit 2048 MB)")

    os.makedirs(OUT, exist_ok=True)
    tag = "numba" if white.USE_NUMBA_SEARCH else "python"
    path = os.path.join(OUT, f"trajectory-{tag}{os.environ.get('LG_TAG','')}.csv")
    with open(path, "w") as handle:
        handle.write("ply,fullmove,side,clock_in_ms,budget_ms,used_ms,clock_out_ms,depth,nodes,fen\n")
        for row in rows:
            handle.write(
                f"{row[0]},{row[1]},{'w' if row[2] else 'b'},{row[3]:.1f},{row[4]:.1f},"
                f"{row[5]:.1f},{row[6]:.1f},{row[7]},{row[8]},{row[9]}\n"
            )
    print(f"wrote {path}")


def run_small(mod: types.ModuleType) -> None:
    """What happens when time_left_ms is tiny. A panic path that itself takes longer
    than the clock left is a flag."""
    fens = {
        "middlegame": "r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6",
        "sharp": "r2q1rk1/pp1bbppp/2np1n2/4p3/2B1P3/2NP1N2/PPPB1PPP/R2Q1RK1 w - - 4 10",
        "krk": "4R3/8/8/3k1K2/8/8/8/8 w - - 15 83",
    }
    budget_fn = numba_budget_ms if mod.USE_NUMBA_SEARCH else python_budget_ms
    points = [3100, 3000, 2999, 2000, 1000, 500, 200, 100, 50, 10, 1, 0]
    print(f"\n{'position':<11} {'clock':>6} {'budget':>8} {'used':>8} {'ratio':>7} "
          f"{'overrun':>9} {'d':>3} {'move':>6}")
    worst = (0.0, "")
    for name, fen in fens.items():
        for clock in points:
            mod.game_board = None
            mod.position_counts_py.clear()
            mod.position_counts_numba.clear()
            uci, used, depth, _nodes, _err = timed_move(mod, fen, clock)
            budget, _panic = budget_fn(float(clock))
            ratio = used / budget if budget > 0 else float("inf")
            over = used - clock
            flag = "  FLAG" if over > 0 else ""
            if used > worst[0]:
                worst = (used, f"{name} @ {clock} ms")
            print(f"{name:<11} {clock:>6} {budget:>7.0f}m {used:>7.1f}m {ratio:>7.2f} "
                  f"{over:>+8.1f}m {depth:>3} {uci:>6}{flag}")
    print(f"\nslowest small-clock reply: {worst[0]:.1f} ms  ({worst[1]})")


def main() -> None:
    print("engine snapshot:", SNAP)
    for name in ("agent.py", "search.py", "nsearch.py", "bitboard.py", "evaluation.py"):
        print(f"  {sha256(os.path.join(SNAP, name))}  {name}")
    print(f"python {sys.version.split()[0]}  chess {chess.__version__}")
    print(f"CHESSATHON_REQUIRE_NUMBA={os.environ.get('CHESSATHON_REQUIRE_NUMBA')}  "
          f"USE_NUMBA_SEARCH={os.environ.get('USE_NUMBA_SEARCH')}")
    t0 = time.monotonic()
    white = load_agent("agent_white")
    black = load_agent("agent_black")
    print(f"import + JIT: {time.monotonic()-t0:.1f}s   rss {rss_mb():.0f} MB")
    nsearch = sys.modules["nsearch"] if "nsearch" in sys.modules else None
    if nsearch is None:
        import search as _s  # noqa: F401

        class _Stub:
            TT_SIZE = 1
            tt_keys = __import__("numpy").zeros(1, dtype="uint64")

        nsearch = _Stub()  # type: ignore[assignment]

    if PHASE in ("game", "both"):
        run_game(white, black, nsearch)
    if PHASE in ("small", "both"):
        run_small(white)


if __name__ == "__main__":
    main()
