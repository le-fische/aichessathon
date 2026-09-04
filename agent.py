import chess

import search


def get_move(fen: str, time_left_ms: int) -> str:
    """Return a legal move in UCI notation."""
    try:
        board = chess.Board(fen)
        try:
            fallback_move = next(iter(board.legal_moves)).uci()
        except StopIteration:
            fallback_move = "e2e4"

        move_str = search.get_move(fen, time_left_ms)

        if chess.Move.from_uci(move_str) not in board.legal_moves:
            return fallback_move

        return move_str
    except Exception:
        try:
            board2 = chess.Board(fen)
            return next(iter(board2.legal_moves)).uci()
        except Exception:
            return "e2e4"
