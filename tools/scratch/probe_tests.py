import sys
import chess
import collections

from nsearch import from_chess_board, see, clear_tt, numba_search, tt_keys, tt_depths, tt_scores, tt_flags, tt_moves
import numpy as np, time

def test_see_pinned():
    fen = "4k3/8/8/3pr3/8/8/8/3QR1K1 w - - 0 1"
    board = chess.Board(fen)
    pieces, colors, state = from_chess_board(board)
    move = (3) | (35 << 6) | (6 << 12) | (4 << 15) | (0 << 18)  # promo=6 (NONE)
    score = see(pieces, colors, state, move)
    print(f"SEE Pinned Test: {score} (expected 100)")

test_see_pinned()
