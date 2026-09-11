import chess, collections, time
from nsearch import get_move_with_info, clear_tt
fen = "r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8"
board = chess.Board(fen)
clear_tt()
t0 = time.monotonic()
uci, score, nodes = get_move_with_info(board, 9999999, collections.Counter(), max_depth=3)
print(f"Nodes: {nodes}, Time: {time.monotonic() - t0:.2f}s")
