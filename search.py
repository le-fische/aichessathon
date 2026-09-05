import os
import time
import typing

import chess

from evaluation import evaluate


class TimeUp(Exception):
    pass


class SearchContext:
    def __init__(self, board: chess.Board, time_budget: float):
        self.board = board
        self.start_time = time.monotonic()
        self.time_budget = time_budget
        self.nodes = 0
        self.hard_stop = time_budget * 0.85
        self.killers: list[list[chess.Move]] = [[] for _ in range(128)]
        self.history_table: list[list[int]] = [[0] * 64 for _ in range(64)]
        max_nodes_env = os.environ.get("SEARCH_MAX_NODES")
        self.max_nodes = int(max_nodes_env) if max_nodes_env else None
        self.path_keys = [board._transposition_key()]

    def check_time(self) -> None:
        self.nodes += 1
        if self.max_nodes is not None:
            if self.nodes >= self.max_nodes:
                raise TimeUp()
            return
        if self.nodes % 256 == 0 and (time.monotonic() - self.start_time) * 1000 >= self.hard_stop:
            raise TimeUp()


TT_EXACT = 0
TT_LOWER = 1
TT_UPPER = 2
MATE_VALUE = 30000

PIECE_VALUE = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}


tt: dict[typing.Any, tuple[int, float, int, str | None]] = {}


def clear_tt_if_full() -> None:
    if len(tt) > 1_500_000:
        tt.clear()


def qsearch(ctx: SearchContext, alpha: float, beta: float, ply: int) -> float:
    ctx.check_time()

    if ply >= 127:
        return evaluate(ctx.board)

    in_check = ctx.board.is_check()
    stand_pat = -float("inf")

    if not in_check:
        stand_pat = evaluate(ctx.board)
        if stand_pat >= beta:
            return stand_pat
        if alpha < stand_pat:
            alpha = stand_pat

    if in_check:
        moves = list(ctx.board.generate_legal_moves())
        if not moves:
            return float(-(MATE_VALUE - ply))
    else:
        moves = list(ctx.board.generate_legal_captures())
        for m in ctx.board.generate_legal_moves(
            from_mask=chess.BB_RANK_7 | chess.BB_RANK_2, to_mask=chess.BB_RANK_8 | chess.BB_RANK_1
        ):
            if m.promotion and not ctx.board.is_capture(m):
                moves.append(m)

    if not moves:
        return stand_pat

    move_scores = []
    for m in moves:
        if m.promotion:
            score = 9000000 + PIECE_VALUE[m.promotion]
        elif ctx.board.is_capture(m):
            victim = ctx.board.piece_type_at(m.to_square)
            if victim is None:
                victim = chess.PAWN
            aggressor = ctx.board.piece_type_at(m.from_square)
            ag_val = PIECE_VALUE[aggressor] if aggressor else 100
            score = 8000000 + PIECE_VALUE[victim] * 10 - ag_val
        else:
            score = 0
        move_scores.append((score, m))

    move_scores.sort(key=lambda x: x[0], reverse=True)
    moves = [m for _, m in move_scores]

    best_score = -float("inf") if in_check else stand_pat

    for move in moves:
        if not in_check and not move.promotion:
            victim = ctx.board.piece_type_at(move.to_square)
            if victim is None:
                victim = chess.PAWN
            if stand_pat + PIECE_VALUE[victim] + 200 < alpha:
                continue

        ctx.board.push(move)
        child_score = -qsearch(ctx, -beta, -alpha, ply + 1)
        ctx.board.pop()

        if child_score > best_score:
            best_score = child_score
        if child_score > alpha:
            alpha = child_score
        if alpha >= beta:
            break

    return best_score


CONTEMPT = 0.0


def get_draw_score(ply: int) -> float:
    return -CONTEMPT if ply % 2 == 0 else CONTEMPT


def negamax(
    ctx: SearchContext, depth: int, ply: int, alpha: float, beta: float, prev_is_null: bool = False
) -> float:
    ctx.check_time()

    hash_key = ctx.board._transposition_key()
    if hash_key in ctx.path_keys:
        return get_draw_score(ply)

    halfmove = ctx.board.halfmove_clock
    if halfmove >= 100:
        return get_draw_score(ply)
    if halfmove >= 4 and ctx.board.is_repetition(3):
        return get_draw_score(ply)
    if len(ctx.board.piece_map()) <= 4 and ctx.board.is_insufficient_material():
        return get_draw_score(ply)

    hash_key = ctx.board._transposition_key()
    tt_entry = tt.get(hash_key)
    tt_move = None
    orig_alpha = alpha

    if tt_entry is not None:
        tt_depth, tt_score, tt_flag, tt_move_uci = tt_entry
        if tt_move_uci:
            tt_move = chess.Move.from_uci(tt_move_uci)

        if tt_depth >= depth:
            score = tt_score
            if score >= MATE_VALUE - 1000:
                score -= ply
            elif score <= -MATE_VALUE + 1000:
                score += ply

            if tt_flag == TT_EXACT:
                return score
            if tt_flag == TT_LOWER and score > alpha:
                alpha = score
            if tt_flag == TT_UPPER and score < beta:
                beta = score
            if alpha >= beta:
                return score

    if depth == 0:
        return qsearch(ctx, alpha, beta, ply)

    ctx.path_keys.append(hash_key)
    in_check = ctx.board.is_check()

    if not in_check and depth >= 3 and not prev_is_null:
        has_non_pawn = bool(
            ctx.board.pieces(chess.KNIGHT, ctx.board.turn)
            | ctx.board.pieces(chess.BISHOP, ctx.board.turn)
            | ctx.board.pieces(chess.ROOK, ctx.board.turn)
            | ctx.board.pieces(chess.QUEEN, ctx.board.turn)
        )
        if has_non_pawn:
            ctx.board.push(chess.Move.null())
            null_score = -negamax(ctx, depth - 3, ply + 1, -beta, -beta + 1, True)
            ctx.board.pop()
            if null_score >= beta:
                ctx.path_keys.pop()
                return null_score

    moves = list(ctx.board.legal_moves)
    if not moves:
        ctx.path_keys.pop()
        if ctx.board.is_check():
            return float(-(MATE_VALUE - ply))
        return 0.0

    best_score = -float("inf")
    current_best_move = None

    move_scores = []
    for m in moves:
        score = 0
        if m == tt_move:
            score = 10000000
        elif m.promotion:
            score = 9000000 + PIECE_VALUE[m.promotion]
        elif ctx.board.is_capture(m):
            victim = ctx.board.piece_type_at(m.to_square)
            if victim is None:
                victim = chess.PAWN
            aggressor = ctx.board.piece_type_at(m.from_square)
            ag_val = PIECE_VALUE[aggressor] if aggressor else 100
            score = 8000000 + PIECE_VALUE[victim] * 10 - ag_val
        else:
            if m in ctx.killers[ply]:
                score = 7000000 if ctx.killers[ply][0] == m else 6000000
            else:
                score = ctx.history_table[m.from_square][m.to_square]
        move_scores.append((score, m))

    move_scores.sort(key=lambda x: x[0], reverse=True)
    moves = [m for _, m in move_scores]

    for move_idx, move in enumerate(moves):
        is_capture = ctx.board.is_capture(move)
        is_quiet = not is_capture and not move.promotion and move not in ctx.killers[ply]

        ctx.board.push(move)

        needs_full_search = True
        if (
            move_idx >= 3
            and depth >= 3
            and not in_check
            and is_quiet
        ):
            reduced_score = -negamax(ctx, depth - 2, ply + 1, -alpha - 1, -alpha)
            if reduced_score > alpha:
                needs_full_search = True
            else:
                score = reduced_score
                needs_full_search = False

        if needs_full_search:
            score = -negamax(ctx, depth - 1, ply + 1, -beta, -alpha)

        ctx.board.pop()

        if score > best_score:
            best_score = score
            current_best_move = move

        if score > alpha:
            alpha = score

        if alpha >= beta:
            if not is_capture:
                if move not in ctx.killers[ply]:
                    ctx.killers[ply].insert(0, move)
                    if len(ctx.killers[ply]) > 2:
                        ctx.killers[ply].pop()
                ctx.history_table[move.from_square][move.to_square] += depth * depth
            break

    store_score = best_score
    if store_score >= MATE_VALUE - 1000:
        store_score += ply
    elif store_score <= -MATE_VALUE + 1000:
        store_score -= ply

    flag = TT_EXACT
    if best_score <= orig_alpha:
        flag = TT_UPPER
    elif best_score >= beta:
        flag = TT_LOWER

    clear_tt_if_full()
    best_uci = current_best_move.uci() if current_best_move else None
    tt[hash_key] = (depth, store_score, flag, best_uci)

    ctx.path_keys.pop()
    return best_score


completed_depth = 0


def get_move(board: chess.Board, time_left_ms: int) -> str:
    global completed_depth
    completed_depth = 0
    board = board.copy()

    # Reverted from a moves-to-go budget on 2026-09-05. That policy kept more
    # clock in reserve but bought it by thinking less early: measured against
    # this one it was a full ply shallower on 7 of 12 clock points, all of them
    # in the first two thirds of the game. Depth in the opening and middlegame
    # decides more games than clock left at the end.
    # See runs/2026-09-05-clock/FINDINGS.md.
    if time_left_ms < 3000:
        budget_ms = min(200.0, time_left_ms * 0.1)
        panic = True
    else:
        budget_ms = min(time_left_ms * 0.045 + 400.0, time_left_ms * 0.25)
        panic = False

    ctx = SearchContext(board, budget_ms)

    moves = list(board.legal_moves)
    if not moves:
        return "0000"

    best_move = moves[0]

    try:
        depth = 1
        prev_score = -float("inf")
        while depth <= 64:
            if len(moves) > 1 and best_move in moves:
                moves.remove(best_move)
                moves.insert(0, best_move)

            if depth >= 4 and abs(prev_score) < MATE_VALUE - 1000:
                alpha = prev_score - 30
                beta = prev_score + 30
                delta = 30
            else:
                alpha = -float("inf")
                beta = float("inf")
                delta = 0

            while True:
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

                    if alpha >= beta:
                        break

                if delta > 0 and (
                    current_best_score <= prev_score - delta or current_best_score >= beta
                ):
                    if delta == 30:
                        delta = 60
                        alpha = prev_score - delta
                        beta = prev_score + delta
                        continue
                    else:
                        alpha = -float("inf")
                        beta = float("inf")
                        delta = 0
                        continue
                break

            prev_score = current_best_score

            best_move = current_best_move
            completed_depth = depth

            if panic:
                break

            if ctx.max_nodes is not None:
                if ctx.nodes >= ctx.max_nodes / 2:
                    break
            else:
                if (time.monotonic() - ctx.start_time) * 1000 > budget_ms / 2:
                    break

            depth += 1

    except (TimeUp, RecursionError):
        pass

    return best_move.uci()
