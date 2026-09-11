"""Probe a position with the transposition table in the state a real game leaves it.

The naive probe clears the table first, which is exactly the condition where
depth-preferred replacement cannot differ from always-replace. The table only
saturates across a long game -- 99.71 percent occupancy by ply 280 -- so the
change has to be judged after the table has been filled the way the game filled
it. This replays every preceding ply at a small budget, then searches the target
position at the real clock without clearing.
"""
import collections, os, sys, time
os.environ["CHESSATHON_REQUIRE_NUMBA"] = "1"
build, pgn_file, clock_ms, good, bad = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5]
sys.path.insert(0, os.path.abspath(build))

import chess
from nsearch import clear_tt, get_move_with_info, from_chess_board

lines = open(pgn_file).read().strip().split("\n")
board = chess.Board(lines[0])
moves = lines[1].split()

clear_tt()
get_move_with_info(chess.Board(lines[0]), 2000, collections.Counter())  # JIT
clear_tt()

counts = collections.Counter()
target_fen = None
t0 = time.perf_counter()
for san in moves:
    if san == bad and board.turn == chess.WHITE:
        target_fen = board.fen()
        break
    # Search each ply briefly so the table fills as a real game fills it.
    get_move_with_info(board.copy(), 4000, counts)
    board.push_san(san)
    counts[int(from_chess_board(board)[2][4])] += 1   # repetition keys are zobrist hashes, not FENs
fill = time.perf_counter() - t0

b = chess.Board(target_fen)
t0 = time.perf_counter()
uci, score, nodes = get_move_with_info(b, clock_ms, counts)
dt = (time.perf_counter() - t0) * 1000
san = b.san(chess.Move.from_uci(uci))
print(f"{build}")
print(f"  table filled by replaying {len(board.move_stack)} plies ({fill:.0f}s)")
print(f"  chose {san:<8} score {score:>7.0f}  nodes {nodes:>10,}  {dt:6.0f}ms")
print(f"  expected {good}, game played {bad}  ->  {'GOOD' if san == good else 'still the bad move' if san == bad else 'neither'}")
