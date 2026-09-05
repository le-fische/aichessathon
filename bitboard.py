# mypy: ignore-errors
# Numba JIT arrays and integer types do not play nicely with mypy strict mode;
# typing is enforced strictly by Numba at JIT compilation time instead.
import chess
import numpy as np
from numba import njit

import evaluation

PAWN = 0
KNIGHT = 1
BISHOP = 2
ROOK = 3
QUEEN = 4
KING = 5
NONE = 6

WHITE = 0
BLACK = 1

CR_WK = 1
CR_WQ = 2
CR_BK = 4
CR_BQ = 8


@njit(cache=False)
def popcount(x):
    count = 0
    while x:
        count += 1
        x &= x - np.uint64(1)
    return count


@njit(cache=False)
def lsb(x):
    return popcount((x & -x) - np.uint64(1))


@njit(cache=False)
def msb(x):
    x = np.uint64(x)
    x |= x >> np.uint64(1)
    x |= x >> np.uint64(2)
    x |= x >> np.uint64(4)
    x |= x >> np.uint64(8)
    x |= x >> np.uint64(16)
    x |= x >> np.uint64(32)
    return popcount(x) - 1


@njit(cache=False)
def init_tables():
    knight_attacks = np.zeros(64, dtype=np.uint64)
    king_attacks = np.zeros(64, dtype=np.uint64)
    pawn_attacks = np.zeros((2, 64), dtype=np.uint64)
    rays = np.zeros((64, 8), dtype=np.uint64)

    for sq in range(64):
        r = sq // 8
        f = sq % 8

        k_a = np.uint64(0)
        for dr, df in [(2, 1), (1, 2), (-1, 2), (-2, 1), (-2, -1), (-1, -2), (1, -2), (2, -1)]:
            nr, nf = r + dr, f + df
            if 0 <= nr < 8 and 0 <= nf < 8:
                k_a |= np.uint64(1) << np.uint64(nr * 8 + nf)
        knight_attacks[sq] = k_a

        kg_a = np.uint64(0)
        for dr in [-1, 0, 1]:
            for df in [-1, 0, 1]:
                if dr == 0 and df == 0:
                    continue
                nr, nf = r + dr, f + df
                if 0 <= nr < 8 and 0 <= nf < 8:
                    kg_a |= np.uint64(1) << np.uint64(nr * 8 + nf)
        king_attacks[sq] = kg_a

        if r < 7:
            if f > 0:
                pawn_attacks[WHITE][sq] |= np.uint64(1) << np.uint64((r + 1) * 8 + f - 1)
            if f < 7:
                pawn_attacks[WHITE][sq] |= np.uint64(1) << np.uint64((r + 1) * 8 + f + 1)
        if r > 0:
            if f > 0:
                pawn_attacks[BLACK][sq] |= np.uint64(1) << np.uint64((r - 1) * 8 + f - 1)
            if f < 7:
                pawn_attacks[BLACK][sq] |= np.uint64(1) << np.uint64((r - 1) * 8 + f + 1)

        dirs = [(1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (-1, 1), (-1, -1), (1, -1)]
        for i, (dr, df) in enumerate(dirs):
            ray = np.uint64(0)
            nr, nf = r + dr, f + df
            while 0 <= nr < 8 and 0 <= nf < 8:
                ray |= np.uint64(1) << np.uint64(nr * 8 + nf)
                nr += dr
                nf += df
            rays[sq][i] = ray

    return knight_attacks, king_attacks, pawn_attacks, rays


KNIGHT_ATTACKS, KING_ATTACKS, PAWN_ATTACKS, RAYS = init_tables()

ROOK_DIRS = np.array([0, 1, 2, 3], dtype=np.int32)
ROOK_POS = np.array([True, True, False, False], dtype=np.bool_)
BISHOP_DIRS = np.array([4, 5, 6, 7], dtype=np.int32)
BISHOP_POS = np.array([True, False, False, True], dtype=np.bool_)
QUEEN_DIRS = np.array([0, 1, 2, 3, 4, 5, 6, 7], dtype=np.int32)
QUEEN_POS = np.array([True, True, False, False, True, False, False, True], dtype=np.bool_)


@njit(cache=False)
def get_slider_attacks(sq, blockers, dirs, is_positive):
    attacks = np.uint64(0)
    for i in range(len(dirs)):
        d = dirs[i]
        pos = is_positive[i]
        ray = RAYS[sq][d]
        masked = ray & blockers
        if masked == 0:
            attacks |= ray
        else:
            blocker_sq = lsb(masked) if pos else msb(masked)
            attacks |= ray ^ RAYS[blocker_sq][d]
    return attacks


@njit(cache=False)
def get_rook_attacks(sq, blockers):
    return get_slider_attacks(sq, blockers, ROOK_DIRS, ROOK_POS)


@njit(cache=False)
def get_bishop_attacks(sq, blockers):
    return get_slider_attacks(sq, blockers, BISHOP_DIRS, BISHOP_POS)


@njit(cache=False)
def get_queen_attacks(sq, blockers):
    return get_slider_attacks(sq, blockers, QUEEN_DIRS, QUEEN_POS)


@njit(cache=False)
def encode_move(fr, to, promo, piece_moved, captured, ep, castle):
    return np.uint32(
        fr
        | (to << 6)
        | (promo << 12)
        | (piece_moved << 15)
        | (captured << 18)
        | (ep << 21)
        | (castle << 22)
    )


@njit(cache=False)
def is_square_attacked(sq, color, pieces, colors):
    blockers = colors[WHITE] | colors[BLACK]

    if color == WHITE:
        if PAWN_ATTACKS[BLACK][sq] & pieces[PAWN] & colors[WHITE]:
            return True
    else:
        if PAWN_ATTACKS[WHITE][sq] & pieces[PAWN] & colors[BLACK]:
            return True

    if KNIGHT_ATTACKS[sq] & pieces[KNIGHT] & colors[color]:
        return True
    if KING_ATTACKS[sq] & pieces[KING] & colors[color]:
        return True

    b_attacks = get_bishop_attacks(sq, blockers)
    if b_attacks & (pieces[BISHOP] | pieces[QUEEN]) & colors[color]:
        return True

    r_attacks = get_rook_attacks(sq, blockers)
    return bool(r_attacks & (pieces[ROOK] | pieces[QUEEN]) & colors[color])


@njit(cache=False)
def generate_pseudo_legal_moves(pieces, colors, state, moves):
    turn = state[0]
    opp = turn ^ 1

    us_pieces = colors[turn]
    them_pieces = colors[opp]
    all_pieces = us_pieces | them_pieces

    count = 0
    ep_square = state[2]

    for pt in range(6):
        bb = pieces[pt] & us_pieces
        while bb:
            sq = lsb(bb)
            bb &= bb - np.uint64(1)

            if pt == PAWN:
                if turn == WHITE:
                    to = sq + 8
                    if (all_pieces & (np.uint64(1) << np.uint64(to))) == 0:
                        promo = to >= 56
                        if promo:
                            moves[count] = encode_move(sq, to, QUEEN, PAWN, NONE, 0, 0)
                            count += 1
                            moves[count] = encode_move(sq, to, ROOK, PAWN, NONE, 0, 0)
                            count += 1
                            moves[count] = encode_move(sq, to, BISHOP, PAWN, NONE, 0, 0)
                            count += 1
                            moves[count] = encode_move(sq, to, KNIGHT, PAWN, NONE, 0, 0)
                            count += 1
                        else:
                            moves[count] = encode_move(sq, to, NONE, PAWN, NONE, 0, 0)
                            count += 1
                            if sq < 16:
                                to2 = sq + 16
                                if (all_pieces & (np.uint64(1) << np.uint64(to2))) == 0:
                                    moves[count] = encode_move(sq, to2, NONE, PAWN, NONE, 0, 0)
                                    count += 1

                    attacks = PAWN_ATTACKS[WHITE][sq] & them_pieces
                    while attacks:
                        to = lsb(attacks)
                        attacks &= attacks - np.uint64(1)
                        cap = NONE
                        for cpt in range(6):
                            if pieces[cpt] & (np.uint64(1) << np.uint64(to)):
                                cap = cpt
                                break
                        promo = to >= 56
                        if promo:
                            moves[count] = encode_move(sq, to, QUEEN, PAWN, cap, 0, 0)
                            count += 1
                            moves[count] = encode_move(sq, to, ROOK, PAWN, cap, 0, 0)
                            count += 1
                            moves[count] = encode_move(sq, to, BISHOP, PAWN, cap, 0, 0)
                            count += 1
                            moves[count] = encode_move(sq, to, KNIGHT, PAWN, cap, 0, 0)
                            count += 1
                        else:
                            moves[count] = encode_move(sq, to, NONE, PAWN, cap, 0, 0)
                            count += 1

                    if ep_square != 64:  # noqa: SIM102
                        if PAWN_ATTACKS[WHITE][sq] & (np.uint64(1) << np.uint64(ep_square)):
                            moves[count] = encode_move(sq, ep_square, NONE, PAWN, PAWN, 1, 0)
                            count += 1
                else:
                    to = sq - 8
                    if (all_pieces & (np.uint64(1) << np.uint64(to))) == 0:
                        promo = to < 8
                        if promo:
                            moves[count] = encode_move(sq, to, QUEEN, PAWN, NONE, 0, 0)
                            count += 1
                            moves[count] = encode_move(sq, to, ROOK, PAWN, NONE, 0, 0)
                            count += 1
                            moves[count] = encode_move(sq, to, BISHOP, PAWN, NONE, 0, 0)
                            count += 1
                            moves[count] = encode_move(sq, to, KNIGHT, PAWN, NONE, 0, 0)
                            count += 1
                        else:
                            moves[count] = encode_move(sq, to, NONE, PAWN, NONE, 0, 0)
                            count += 1
                            if sq >= 48:
                                to2 = sq - 16
                                if (all_pieces & (np.uint64(1) << np.uint64(to2))) == 0:
                                    moves[count] = encode_move(sq, to2, NONE, PAWN, NONE, 0, 0)
                                    count += 1

                    attacks = PAWN_ATTACKS[BLACK][sq] & them_pieces
                    while attacks:
                        to = lsb(attacks)
                        attacks &= attacks - np.uint64(1)
                        cap = NONE
                        for cpt in range(6):
                            if pieces[cpt] & (np.uint64(1) << np.uint64(to)):
                                cap = cpt
                                break
                        promo = to < 8
                        if promo:
                            moves[count] = encode_move(sq, to, QUEEN, PAWN, cap, 0, 0)
                            count += 1
                            moves[count] = encode_move(sq, to, ROOK, PAWN, cap, 0, 0)
                            count += 1
                            moves[count] = encode_move(sq, to, BISHOP, PAWN, cap, 0, 0)
                            count += 1
                            moves[count] = encode_move(sq, to, KNIGHT, PAWN, cap, 0, 0)
                            count += 1
                        else:
                            moves[count] = encode_move(sq, to, NONE, PAWN, cap, 0, 0)
                            count += 1

                    if ep_square != 64:  # noqa: SIM102
                        if PAWN_ATTACKS[BLACK][sq] & (np.uint64(1) << np.uint64(ep_square)):
                            moves[count] = encode_move(sq, ep_square, NONE, PAWN, PAWN, 1, 0)
                            count += 1
            else:
                attacks = np.uint64(0)
                if pt == KNIGHT:
                    attacks = KNIGHT_ATTACKS[sq]
                elif pt == BISHOP:
                    attacks = get_bishop_attacks(sq, all_pieces)
                elif pt == ROOK:
                    attacks = get_rook_attacks(sq, all_pieces)
                elif pt == QUEEN:
                    attacks = get_queen_attacks(sq, all_pieces)
                elif pt == KING:
                    attacks = KING_ATTACKS[sq]

                attacks &= ~us_pieces

                while attacks:
                    to = lsb(attacks)
                    attacks &= attacks - np.uint64(1)

                    cap = NONE
                    if (np.uint64(1) << np.uint64(to)) & them_pieces:
                        for cpt in range(6):
                            if pieces[cpt] & (np.uint64(1) << np.uint64(to)):
                                cap = cpt
                                break
                    moves[count] = encode_move(sq, to, NONE, pt, cap, 0, 0)
                    count += 1

    castling = state[1]
    if turn == WHITE:
        if (
            (castling & CR_WK)
            and not (all_pieces & np.uint64(0x60))
            and not is_square_attacked(4, BLACK, pieces, colors)
            and not is_square_attacked(5, BLACK, pieces, colors)
        ):
            moves[count] = encode_move(4, 6, NONE, KING, NONE, 0, 1)
            count += 1
        if (
            (castling & CR_WQ)
            and not (all_pieces & np.uint64(0xE))
            and not is_square_attacked(4, BLACK, pieces, colors)
            and not is_square_attacked(3, BLACK, pieces, colors)
        ):
            moves[count] = encode_move(4, 2, NONE, KING, NONE, 0, 1)
            count += 1
    else:
        if (
            (castling & CR_BK)
            and not (all_pieces & np.uint64(0x6000000000000000))
            and not is_square_attacked(60, WHITE, pieces, colors)
            and not is_square_attacked(61, WHITE, pieces, colors)
        ):
            moves[count] = encode_move(60, 62, NONE, KING, NONE, 0, 1)
            count += 1
        if (
            (castling & CR_BQ)
            and not (all_pieces & np.uint64(0x0E00000000000000))
            and not is_square_attacked(60, WHITE, pieces, colors)
            and not is_square_attacked(59, WHITE, pieces, colors)
        ):
            moves[count] = encode_move(60, 58, NONE, KING, NONE, 0, 1)
            count += 1

    return count


@njit(cache=False)
def make_move(pieces, colors, state, move, undo):
    fr = move & 0x3F
    to = (move >> 6) & 0x3F
    promo = (move >> 12) & 0x7
    piece_moved = (move >> 15) & 0x7
    captured = (move >> 18) & 0x7
    ep = (move >> 21) & 0x1
    castle = (move >> 22) & 0x1

    turn = state[0]
    opp = turn ^ 1

    undo[0] = state[1]
    undo[1] = state[2]
    undo[2] = state[3]

    state[0] = opp
    state[2] = 64
    if piece_moved == PAWN or captured != NONE:
        state[3] = 0
    else:
        state[3] += 1

    fr_mask = np.uint64(1) << np.uint64(fr)
    to_mask = np.uint64(1) << np.uint64(to)

    pieces[piece_moved] ^= fr_mask | to_mask
    colors[turn] ^= fr_mask | to_mask

    if captured != NONE:
        if ep:
            cap_sq = to - 8 if turn == WHITE else to + 8
            cap_mask = np.uint64(1) << np.uint64(cap_sq)
            pieces[PAWN] ^= cap_mask
            colors[opp] ^= cap_mask
        else:
            pieces[captured] ^= to_mask
            colors[opp] ^= to_mask

    if promo != NONE:
        pieces[PAWN] ^= to_mask
        pieces[promo] ^= to_mask

    if castle:
        if to == 6:
            pieces[ROOK] ^= (np.uint64(1) << np.uint64(7)) | (np.uint64(1) << np.uint64(5))
            colors[WHITE] ^= (np.uint64(1) << np.uint64(7)) | (np.uint64(1) << np.uint64(5))
        elif to == 2:
            pieces[ROOK] ^= (np.uint64(1) << np.uint64(0)) | (np.uint64(1) << np.uint64(3))
            colors[WHITE] ^= (np.uint64(1) << np.uint64(0)) | (np.uint64(1) << np.uint64(3))
        elif to == 62:
            pieces[ROOK] ^= (np.uint64(1) << np.uint64(63)) | (np.uint64(1) << np.uint64(61))
            colors[BLACK] ^= (np.uint64(1) << np.uint64(63)) | (np.uint64(1) << np.uint64(61))
        elif to == 58:
            pieces[ROOK] ^= (np.uint64(1) << np.uint64(56)) | (np.uint64(1) << np.uint64(59))
            colors[BLACK] ^= (np.uint64(1) << np.uint64(56)) | (np.uint64(1) << np.uint64(59))

    if piece_moved == PAWN and abs(to - fr) == 16:
        state[2] = fr + 8 if turn == WHITE else fr - 8

    if state[1]:
        if piece_moved == KING:
            if turn == WHITE:
                state[1] &= ~(CR_WK | CR_WQ)
            else:
                state[1] &= ~(CR_BK | CR_BQ)
        if fr == 0 or to == 0:
            state[1] &= ~CR_WQ
        if fr == 7 or to == 7:
            state[1] &= ~CR_WK
        if fr == 56 or to == 56:
            state[1] &= ~CR_BQ
        if fr == 63 or to == 63:
            state[1] &= ~CR_BK

    king_sq = lsb(pieces[KING] & colors[turn])
    return not is_square_attacked(king_sq, opp, pieces, colors)


@njit(cache=False)
def unmake_move(pieces, colors, state, move, undo):
    fr = move & 0x3F
    to = (move >> 6) & 0x3F
    promo = (move >> 12) & 0x7
    piece_moved = (move >> 15) & 0x7
    captured = (move >> 18) & 0x7
    ep = (move >> 21) & 0x1
    castle = (move >> 22) & 0x1

    state[0] ^= 1
    turn = state[0]
    opp = turn ^ 1

    state[1] = undo[0]
    state[2] = undo[1]
    state[3] = undo[2]

    fr_mask = np.uint64(1) << np.uint64(fr)
    to_mask = np.uint64(1) << np.uint64(to)

    pieces[piece_moved] ^= fr_mask | to_mask
    colors[turn] ^= fr_mask | to_mask

    if promo != NONE:
        pieces[PAWN] ^= to_mask
        pieces[promo] ^= to_mask

    if captured != NONE:
        if ep:
            cap_sq = to - 8 if turn == WHITE else to + 8
            cap_mask = np.uint64(1) << np.uint64(cap_sq)
            pieces[PAWN] ^= cap_mask
            colors[opp] ^= cap_mask
        else:
            pieces[captured] ^= to_mask
            colors[opp] ^= to_mask

    if castle:
        if to == 6:
            pieces[ROOK] ^= (np.uint64(1) << np.uint64(7)) | (np.uint64(1) << np.uint64(5))
            colors[WHITE] ^= (np.uint64(1) << np.uint64(7)) | (np.uint64(1) << np.uint64(5))
        elif to == 2:
            pieces[ROOK] ^= (np.uint64(1) << np.uint64(0)) | (np.uint64(1) << np.uint64(3))
            colors[WHITE] ^= (np.uint64(1) << np.uint64(0)) | (np.uint64(1) << np.uint64(3))
        elif to == 62:
            pieces[ROOK] ^= (np.uint64(1) << np.uint64(63)) | (np.uint64(1) << np.uint64(61))
            colors[BLACK] ^= (np.uint64(1) << np.uint64(63)) | (np.uint64(1) << np.uint64(61))
        elif to == 58:
            pieces[ROOK] ^= (np.uint64(1) << np.uint64(56)) | (np.uint64(1) << np.uint64(59))
            colors[BLACK] ^= (np.uint64(1) << np.uint64(56)) | (np.uint64(1) << np.uint64(59))


@njit(cache=False)
def perft(pieces, colors, state, depth):
    if depth == 0:
        return 1

    moves = np.zeros(256, dtype=np.uint32)
    count = generate_pseudo_legal_moves(pieces, colors, state, moves)

    nodes = 0
    undo = np.zeros(3, dtype=np.int32)

    for i in range(count):
        move = moves[i]
        is_legal = make_move(pieces, colors, state, move, undo)
        if is_legal:
            nodes += perft(pieces, colors, state, depth - 1)
        unmake_move(pieces, colors, state, move, undo)
    return nodes


@njit(cache=False)
def divide(pieces, colors, state, depth):
    moves = np.zeros(256, dtype=np.uint32)
    count = generate_pseudo_legal_moves(pieces, colors, state, moves)

    nodes_per_move = np.zeros(count, dtype=np.uint64)
    valid_moves = np.zeros(256, dtype=np.uint32)
    undo = np.zeros(3, dtype=np.int32)

    total = 0
    valid_count = 0
    for i in range(count):
        move = moves[i]
        is_legal = make_move(pieces, colors, state, move, undo)
        if is_legal:
            nodes = perft(pieces, colors, state, depth - 1)
            nodes_per_move[valid_count] = nodes
            valid_moves[valid_count] = move
            valid_count += 1
            total += nodes
        unmake_move(pieces, colors, state, move, undo)

    return total, valid_moves[:valid_count], nodes_per_move[:valid_count]





EVAL_MG = np.array(evaluation.TABLE_MG, dtype=np.int32)
EVAL_EG = np.array(evaluation.TABLE_EG, dtype=np.int32)
PHASE_INC = np.array(evaluation.gamephase_inc, dtype=np.int32)
CENTRE_DISTANCE = np.array(
    [max(abs((sq % 8) - 3.5), abs((sq // 8) - 3.5)) for sq in range(64)],
    dtype=np.float64
)

@njit(cache=False)
def evaluate(pieces, colors, state):
    mg_diff = 0
    eg_diff = 0
    game_phase = 0
    
    for pt in range(6):
        bb = pieces[pt]
        
        count = popcount(bb)
        game_phase += PHASE_INC[pt + 1] * count
        
        for c in range(2):
            c_mask = bb & colors[c]
            while c_mask:
                sq = lsb(c_mask)
                c_mask &= c_mask - np.uint64(1)
                
                py_c = 1 - c
                py_pt = pt + 1
                
                mg_diff += EVAL_MG[py_c][py_pt][sq]
                eg_diff += EVAL_EG[py_c][py_pt][sq]
                
    turn = state[0]
    if turn == BLACK:
        mg_diff = -mg_diff
        eg_diff = -eg_diff
        
    phase = min(game_phase, 24)
    
    score = float((mg_diff * phase + eg_diff * (24 - phase)) // 24)
    
    if game_phase <= 6:
        white_bare = (colors[WHITE] & ~pieces[KING]) == 0
        black_bare = (colors[BLACK] & ~pieces[KING]) == 0
        
        if white_bare != black_bare:
            winner = WHITE if black_bare else BLACK
            loser = winner ^ 1
            
            loser_king = lsb(pieces[KING] & colors[loser])
            winner_king = lsb(pieces[KING] & colors[winner])
            
            file_gap = abs((winner_king % 8) - (loser_king % 8))
            rank_gap = abs((winner_king // 8) - (loser_king // 8))
            king_gap = file_gap + rank_gap
            
            drive = 16.0 * CENTRE_DISTANCE[loser_king] + 4.0 * (14 - king_gap)
            if turn != winner:
                drive = -drive
            score += drive
            
    return score


def warmup():
    import time

    t0 = time.time()
    board = chess.Board()
    pieces, colors, state = from_chess_board(board)
    divide(pieces, colors, state, 1)
    evaluate(pieces, colors, state)
    t1 = time.time()
    return t1 - t0


def from_chess_board(board):
    pieces = np.zeros(6, dtype=np.uint64)
    colors = np.zeros(2, dtype=np.uint64)
    state = np.zeros(4, dtype=np.int32)

    for sq in range(64):
        piece = board.piece_at(sq)
        if piece:
            pt = piece.piece_type - 1  # PAWN=0, KNIGHT=1, etc.
            color = WHITE if piece.color == chess.WHITE else BLACK
            pieces[pt] |= np.uint64(1) << np.uint64(sq)
            colors[color] |= np.uint64(1) << np.uint64(sq)

    state[0] = WHITE if board.turn == chess.WHITE else BLACK

    c = 0
    if board.has_kingside_castling_rights(chess.WHITE):
        c |= CR_WK
    if board.has_queenside_castling_rights(chess.WHITE):
        c |= CR_WQ
    if board.has_kingside_castling_rights(chess.BLACK):
        c |= CR_BK
    if board.has_queenside_castling_rights(chess.BLACK):
        c |= CR_BQ
    state[1] = c

    state[2] = board.ep_square if board.ep_square is not None else 64
    state[3] = board.halfmove_clock

    return pieces, colors, state


def decode_move(move):
    fr = move & 0x3F
    to = (move >> 6) & 0x3F
    promo = (move >> 12) & 0x7

    promo_str = ""
    if promo == KNIGHT:
        promo_str = "n"
    elif promo == BISHOP:
        promo_str = "b"
    elif promo == ROOK:
        promo_str = "r"
    elif promo == QUEEN:
        promo_str = "q"

    return f"{chess.SQUARE_NAMES[fr]}{chess.SQUARE_NAMES[to]}{promo_str}"
