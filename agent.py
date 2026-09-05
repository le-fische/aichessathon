import chess

import search

game_board: chess.Board | None = None


def get_move(fen: str, time_left_ms: int) -> str:
    """Return a legal move in UCI notation."""
    global game_board

    try:
        if game_board is None:
            game_board = chess.Board(fen)
        elif game_board.fen() != fen:
            matched = False
            for m in list(game_board.legal_moves):
                game_board.push(m)
                if game_board.fen() == fen:
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
        try:
            game_board = chess.Board(fen)
            fallback = next(iter(game_board.legal_moves)).uci()
            game_board.push(chess.Move.from_uci(fallback))
            return fallback
        except Exception:
            return "e2e4"
