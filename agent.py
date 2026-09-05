import traceback

import chess

import search

game_board: chess.Board | None = None

def get_position_fen(fen: str) -> str:
    return " ".join(fen.split(" ")[:4])

def get_move(fen: str, time_left_ms: int) -> str:
    """Return a legal move in UCI notation."""
    global game_board

    try:
        target_pos = get_position_fen(fen)
        if game_board is None:
            game_board = chess.Board(fen)
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

        try:
            fallback_move = next(iter(game_board.legal_moves)).uci()
        except StopIteration:
            fallback_move = "e2e4"

        move_str = search.get_move(game_board, time_left_ms)

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
            fallback = next(iter(game_board.legal_moves)).uci()
            game_board.push(chess.Move.from_uci(fallback))
            return fallback
        except Exception:
            return "e2e4"
