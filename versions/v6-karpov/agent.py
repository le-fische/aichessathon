import collections
import os
import sys
import traceback
from collections.abc import Hashable

import chess
from search import get_move as pysearch_get_move
from search import tt as pysearch_tt

USE_NUMBA_SEARCH = os.environ.get("USE_NUMBA_SEARCH", "0") == "1"
REQUIRE_NUMBA = os.environ.get("CHESSATHON_REQUIRE_NUMBA", "0") == "1"

try:
    from nsearch import clear_tt as nsearch_clear_tt
    from nsearch import get_move as nsearch_get_move
    from nsearch import from_chess_board
    if USE_NUMBA_SEARCH:
        print("agent.py: Numba search successfully imported and active.", file=sys.stderr)
except Exception:
    if USE_NUMBA_SEARCH:
        print("agent.py: Numba import failed. Falling back to Python search.", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        if REQUIRE_NUMBA:
            raise
    USE_NUMBA_SEARCH = False

numba_failed_runtime = False
first_move = True

game_board: chess.Board | None = None
position_counts_py: collections.Counter[Hashable] = collections.Counter()
position_counts_numba: collections.Counter[Hashable] = collections.Counter()

def on_game_start() -> None:
    pysearch_tt.clear()
    if USE_NUMBA_SEARCH and not numba_failed_runtime:
        try:
            nsearch_clear_tt()
        except Exception:
            pass

def get_position_fen(fen: str) -> str:
    return " ".join(fen.split(" ")[:4])

def get_move(fen: str, time_left_ms: int) -> str:
    global game_board
    global position_counts_py
    global position_counts_numba
    global numba_failed_runtime
    global USE_NUMBA_SEARCH
    global first_move

    if first_move:
        if USE_NUMBA_SEARCH and not numba_failed_runtime:
            print("agent.py: Executing get_move using Numba search.", file=sys.stderr)
        else:
            print("agent.py: Executing get_move using Python search.", file=sys.stderr)
        first_move = False

    try:
        target_pos = get_position_fen(fen)
        if game_board is None:
            game_board = chess.Board(fen)
            position_counts_py.clear()
            position_counts_numba.clear()
            on_game_start()
        elif get_position_fen(game_board.fen()) != target_pos:
            matched = False
            for m in list(game_board.legal_moves):
                game_board.push(m)
                if get_position_fen(game_board.fen()) == target_pos:
                    matched = True
                    break
                game_board.pop()
            if not matched:
                game_board = chess.Board(fen)
                position_counts_py.clear()
                position_counts_numba.clear()

        try:
            fallback_move = next(iter(game_board.legal_moves)).uci()
        except StopIteration:
            fallback_move = "e2e4"

        position_counts_py[game_board._transposition_key()] += 1
        if USE_NUMBA_SEARCH:
            _, _, state = from_chess_board(game_board)
            position_counts_numba[state[4]] += 1

        move_str = None
        
        if USE_NUMBA_SEARCH and not numba_failed_runtime:
            try:
                move_str = nsearch_get_move(game_board, time_left_ms, position_counts_numba)
                move_obj = chess.Move.from_uci(move_str)
                if move_obj not in game_board.legal_moves:
                    raise ValueError("Numba search returned illegal move")
            except Exception:
                print("agent.py: Numba get_move failed. Falling back to Python search.", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                if REQUIRE_NUMBA:
                    raise
                numba_failed_runtime = True
                move_str = None
                
        if move_str is None:
            move_str = pysearch_get_move(game_board, time_left_ms, position_counts_py)

        try:
            move_obj = chess.Move.from_uci(move_str)
        except Exception:
            move_obj = chess.Move.from_uci(fallback_move)
            move_str = fallback_move

        if move_obj not in game_board.legal_moves:
            move_obj = chess.Move.from_uci(fallback_move)
            move_str = fallback_move

        game_board.push(move_obj)
        return move_str
    except Exception:
        print("agent.py: Top-level get_move exception.", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        try:
            game_board = chess.Board(fen)
            position_counts_py.clear()
            position_counts_numba.clear()
            fallback = next(iter(game_board.legal_moves)).uci()
            game_board.push(chess.Move.from_uci(fallback))
            return fallback
        except Exception:
            return "e2e4"
