import collections
import os
import traceback
from collections.abc import Hashable

import chess

USE_NUMBA_SEARCH = os.environ.get("USE_NUMBA_SEARCH", "0") == "1"

if USE_NUMBA_SEARCH:
    from nsearch import clear_tt
    from nsearch import get_move as search_get_move
    
    def on_game_start() -> None:
        clear_tt() # type: ignore
else:
    from search import get_move as search_get_move
    from search import tt
    
    def on_game_start() -> None:
        tt.clear()

game_board: chess.Board | None = None
position_counts: collections.Counter[Hashable] = collections.Counter()

def get_position_fen(fen: str) -> str:
    return " ".join(fen.split(" ")[:4])

def get_move(fen: str, time_left_ms: int) -> str:
    """Return a legal move in UCI notation."""
    global game_board
    global position_counts

    try:
        target_pos = get_position_fen(fen)
        if game_board is None:
            game_board = chess.Board(fen)
            position_counts.clear()
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
                position_counts.clear()

        try:
            fallback_move = next(iter(game_board.legal_moves)).uci()
        except StopIteration:
            fallback_move = "e2e4"

        if USE_NUMBA_SEARCH:
            from nsearch import from_chess_board  # type: ignore
            _, _, state = from_chess_board(game_board) # type: ignore
            position_counts[state[4]] += 1
        else:
            position_counts[game_board._transposition_key()] += 1

        move_str = search_get_move(game_board, time_left_ms, position_counts)

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
        traceback.print_exc()
        try:
            game_board = chess.Board(fen)
            position_counts.clear()
            fallback = next(iter(game_board.legal_moves)).uci()
            game_board.push(chess.Move.from_uci(fallback))
            return fallback
        except Exception:
            return "e2e4"
