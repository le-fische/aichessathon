import time

import chess

from evaluation import evaluate


class TimeUp(Exception):
    pass


class SearchContext:
    def __init__(self, board: chess.Board, time_budget: float, history: set[str]):
        self.board = board
        self.start_time = time.monotonic()
        self.time_budget = time_budget
        self.history = history
        self.nodes = 0
        self.hard_stop = time_budget * 0.85

    def check_time(self) -> None:
        self.nodes += 1
        if self.nodes % 2048 == 0 and (time.monotonic() - self.start_time) * 1000 >= self.hard_stop:
            raise TimeUp()


def negamax(
    ctx: SearchContext, depth: int, ply: int, alpha: float, beta: float
) -> float:
    ctx.check_time()

    # Draw checks
    halfmove = ctx.board.halfmove_clock
    if halfmove >= 100:
        return 0.0
    if halfmove >= 4 and ctx.board.is_repetition(2):
        return 0.0
    if len(ctx.board.piece_map()) <= 4 and ctx.board.is_insufficient_material():
        return 0.0

    if depth == 0:
        if ctx.board.is_check() and not any(ctx.board.generate_legal_moves()):
            return -(30000.0 - ply)
        return evaluate(ctx.board)

    moves = list(ctx.board.legal_moves)
    if not moves:
        if ctx.board.is_check():
            return -(30000.0 - ply)
        return 0.0

    best_score = -float("inf")
    
    moves.sort(key=lambda m: ctx.board.is_capture(m), reverse=True)

    for move in moves:
        ctx.board.push(move)
        score = -negamax(ctx, depth - 1, ply + 1, -beta, -alpha)
        ctx.board.pop()

        if score > best_score:
            best_score = score

        if score > alpha:
            alpha = score

        if alpha >= beta:
            break

    return best_score


def get_move(fen: str, time_left_ms: int, history: set[str]) -> str:
    board = chess.Board(fen)

    if time_left_ms < 3000:
        budget_ms = min(200.0, time_left_ms * 0.1)
        panic = True
    else:
        budget_ms = min(time_left_ms * 0.045 + 400.0, time_left_ms * 0.25)
        panic = False

    ctx = SearchContext(board, budget_ms, history)

    moves = list(board.legal_moves)
    if not moves:
        return "0000"

    best_move = moves[0]

    try:
        depth = 1
        while depth <= 64:
            if len(moves) > 1 and best_move in moves:
                moves.remove(best_move)
                moves.insert(0, best_move)

            alpha = -float("inf")
            beta = float("inf")
            current_best_score = -float("inf")
            current_best_move = best_move

            for move in moves:
                ctx.board.push(move)
                score = -negamax(ctx, depth - 1, 1, -beta, -alpha)
                ctx.board.pop()

                if score > current_best_score:
                    current_best_score = score
                    current_best_move = move

                if score > alpha:
                    alpha = score

            best_move = current_best_move

            if panic:
                break
                
            if (time.monotonic() - ctx.start_time) * 1000 > budget_ms / 2:
                break

            depth += 1

    except (TimeUp, RecursionError):
        pass


    return best_move.uci()
