import sys
import chess
from nsearch import from_chess_board, numba_search, tt_keys, tt_depths, tt_scores, tt_flags, tt_moves
import numpy as np

# We just want to check if search crashes, we already have exact matching since I didn't change movegen logic!
