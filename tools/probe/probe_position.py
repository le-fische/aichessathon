"""Run a build on a single position at the real clock budget and report its choice.

Two rated games were thrown away at move 59 with 24 to 26 seconds left, which is
not time trouble and not the panic path. These positions are a seconds-long
proxy for a three-hour gate: if a candidate flips them to the better move, that
is evidence worth gating; if it does not, the candidate has not addressed the
failure the games actually showed.
"""
import collections, os, sys, time
os.environ["CHESSATHON_REQUIRE_NUMBA"] = "1"
build = sys.argv[1]
fen = sys.argv[2]
clock_ms = int(sys.argv[3]) if len(sys.argv) > 3 else 26000
expect_good = sys.argv[4] if len(sys.argv) > 4 else None
expect_bad = sys.argv[5] if len(sys.argv) > 5 else None
sys.path.insert(0, os.path.abspath(build))

import chess
from nsearch import clear_tt, get_move_with_info

board = chess.Board(fen)
clear_tt()
get_move_with_info(chess.Board(fen), 3000, collections.Counter())   # warm the JIT
clear_tt()

t0 = time.perf_counter()
uci, score, nodes = get_move_with_info(board, clock_ms, collections.Counter())
dt = (time.perf_counter() - t0) * 1000

mv = chess.Move.from_uci(uci)
san = board.san(mv)
print(f"{build}")
print(f"  chose {san:<8} ({uci})  score {score:>8.0f}  nodes {nodes:>10,}  {dt:6.0f}ms")
if expect_good and expect_bad:
    verdict = "GOOD" if san == expect_good else ("the known bad move" if san == expect_bad else "neither")
    print(f"  expected {expect_good}, game played {expect_bad}  ->  {verdict}")
