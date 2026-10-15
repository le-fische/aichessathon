# ruff: noqa: E501
# mypy: ignore-errors
import os
import sys
import time
import chess
import numpy as np
from numba import njit, objmode

import bitboard
from bitboard import (
    BISHOP,
    BLACK,
    KING,
    KING_ATTACKS,
    KNIGHT,
    KNIGHT_ATTACKS,
    NONE,
    PAWN,
    PAWN_ATTACKS,
    QUEEN,
    ROOK,
    WHITE,
    decode_move,
    evaluate,
    from_chess_board,
    generate_pseudo_legal_moves,
    get_bishop_attacks,
    get_rook_attacks,
    is_square_attacked,
    lsb,
    make_move,
    unmake_move,
    popcount,
)

# ---------------------------------------------------------------------------
# NNUE v2 Silicon Model Weights Loader
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_W_DIR = os.path.join(_HERE, "weights", "v2_mlp")
if not os.path.exists(_W_DIR):
    _W_DIR = os.path.join(_HERE, "weights")

def _load_or_default(filename, shape, dtype):
    path = os.path.join(_W_DIR, filename)
    if not os.path.exists(path):
        alt_path = os.path.join(_HERE, "weights", filename)
        if os.path.exists(alt_path):
            path = alt_path
    if os.path.exists(path):
        try:
            arr = np.load(path)
            if arr.shape == shape and arr.dtype == dtype:
                return arr
            elif arr.shape == shape:
                return arr.astype(dtype)
        except Exception:
            pass
    return np.zeros(shape, dtype=dtype)

weights_acc = _load_or_default("weights_acc.npy", (768, 256), np.int16)
biases_acc = _load_or_default("biases_acc.npy", (256,), np.int16)
weights_fc1 = _load_or_default("weights_fc1.npy", (64, 512), np.int8)
biases_fc1 = _load_or_default("biases_fc1.npy", (64,), np.int32)
weights_fc2 = _load_or_default("weights_fc2.npy", (8, 64), np.int8)
biases_fc2 = _load_or_default("biases_fc2.npy", (8,), np.int32)

@njit(cache=False)
def nnue_full_refresh(pieces, colors, weights, biases, acc):
    acc[0, :] = biases[:]
    acc[1, :] = biases[:]
    for c in range(2):
        for p in range(6):
            bb = pieces[p] & colors[c]
            while bb:
                sq = bitboard.lsb(bb)
                w_idx = c * 384 + p * 64 + sq
                b_idx = (c ^ 1) * 384 + p * 64 + (sq ^ 56)
                for j in range(256):
                    acc[0, j] += weights[w_idx, j]
                    acc[1, j] += weights[b_idx, j]
                bb &= bb - np.uint64(1)

@njit(cache=False)
def extract_diffs(move, turn, diffs):
    fr = move & 0x3F
    to = (move >> 6) & 0x3F
    promo = (move >> 12) & 0x7
    piece_moved = (move >> 15) & 0x7
    captured = (move >> 18) & 0x7
    ep = (move >> 21) & 0x1
    castle = (move >> 22) & 0x1
    opp = turn ^ 1
    count = 0
    diffs[count, 0] = -1
    diffs[count, 1] = turn
    diffs[count, 2] = piece_moved
    diffs[count, 3] = fr
    count += 1
    diffs[count, 0] = 1
    diffs[count, 1] = turn
    diffs[count, 2] = promo if promo != 6 else piece_moved
    diffs[count, 3] = to
    count += 1
    if captured != 6:
        cap_sq = to
        if ep:
            cap_sq = to - 8 if turn == 0 else to + 8
        diffs[count, 0] = -1
        diffs[count, 1] = opp
        diffs[count, 2] = 0 if ep else captured
        diffs[count, 3] = cap_sq
        count += 1
    if castle:
        if to == 62:  # g8, Black kingside: rook h8 -> f8
            diffs[count, 0] = -1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 63; count += 1
            diffs[count, 0] = 1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 61; count += 1
        elif to == 58:  # c8, Black queenside: rook a8 -> d8
            diffs[count, 0] = -1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 56; count += 1
            diffs[count, 0] = 1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 59; count += 1
        elif to == 6:  # g1, White kingside: rook h1 -> f1
            diffs[count, 0] = -1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 7; count += 1
            diffs[count, 0] = 1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 5; count += 1
        elif to == 2:  # c1, White queenside: rook a1 -> d1
            diffs[count, 0] = -1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 0; count += 1
            diffs[count, 0] = 1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 3; count += 1
    return count

@njit(cache=False)
def apply_diffs(weights, acc, diffs, count):
    for i in range(count):
        sign = diffs[i, 0]
        c = diffs[i, 1]
        p = diffs[i, 2]
        sq = diffs[i, 3]
        w_idx = c * 384 + p * 64 + sq
        b_idx = (c ^ 1) * 384 + p * 64 + (sq ^ 56)
        if sign == 1:
            for j in range(256):
                acc[0, j] += weights[w_idx, j]
                acc[1, j] += weights[b_idx, j]
        else:
            for j in range(256):
                acc[0, j] -= weights[w_idx, j]
                acc[1, j] -= weights[b_idx, j]

@njit(fastmath=True)
def nnue_eval_head(acc, turn, total_pieces, w1, b1, w2, b2):
    opp = turn ^ 1
    bucket = 0
    if total_pieces > 6: bucket = 1
    if total_pieces > 10: bucket = 2
    if total_pieces > 14: bucket = 3
    if total_pieces > 18: bucket = 4
    if total_pieces > 22: bucket = 5
    if total_pieces > 26: bucket = 6
    if total_pieces > 29: bucket = 7

    out = np.int64(b2[bucket])
    w2_b = w2[bucket]
    
    c_acc = np.empty(512, dtype=np.int32)
    for i in range(256):
        v = acc[turn, i]
        c_acc[i] = 0 if v < 0 else (127 if v > 127 else v)
    for i in range(256):
        v = acc[opp, i]
        c_acc[256 + i] = 0 if v < 0 else (127 if v > 127 else v)

    for i in range(64):
        s = np.int64(b1[i])
        w1_row = w1[i]
        for j in range(512):
            s += np.int64(c_acc[j]) * np.int64(w1_row[j])
        s = s // 64
        if s < 0: s = 0
        elif s > 127: s = 127
        if i >= 32:
            s = (s * s) // 127
        out += s * np.int64(w2_b[i])

    return np.int32((out * 173718) // 11117326)

@njit(fastmath=True)
def pure_nnue_eval(pieces, colors, state, acc, w1, b1, w2, b2):
    total_pieces = popcount(colors[0] | colors[1])
    return float(nnue_eval_head(acc, state[0], total_pieces, w1, b1, w2, b2))


# ---------------------------------------------------------------------------
# Search Constants & Transposition Table
# ---------------------------------------------------------------------------
TT_EXACT = 0
TT_LOWER = 1
TT_UPPER = 2
MATE_VALUE = 30000

TT_SIZE = 16777216  # 2^24
tt_keys = np.zeros(TT_SIZE, dtype=np.uint64)
tt_depths = np.zeros(TT_SIZE, dtype=np.int8)
tt_scores = np.zeros(TT_SIZE, dtype=np.float32)
tt_flags = np.zeros(TT_SIZE, dtype=np.uint8)
tt_moves = np.zeros(TT_SIZE, dtype=np.uint32)

PIECE_VALUE = np.array([100, 320, 330, 500, 900, 0, 0], dtype=np.int32)
SEE_VALUE = np.array([100, 320, 330, 500, 900, 10000, 0], dtype=np.int32)
CONTEMPT = 0.0

def clear_tt():
    tt_keys.fill(0)

@njit(cache=False)
def get_draw_score(ply):
    if ply % 2 == 0:
        return -CONTEMPT
    else:
        return CONTEMPT

@njit(cache=False)
def in_check(pieces, colors, state):
    turn = state[0]
    opp = turn ^ 1
    bb = pieces[KING] & colors[turn]
    if bb == 0:
        return False
    king_sq = lsb(bb)
    return is_square_attacked(king_sq, opp, pieces, colors)

@njit(cache=False)
def score_moves(moves, count, tt_move, killers, ply, history_table):
    scores = np.zeros(count, dtype=np.int32)
    for i in range(count):
        m = moves[i]
        if m == tt_move:
            scores[i] = 10000000
            continue
            
        fr = m & 0x3F
        to = (m >> 6) & 0x3F
        promo = (m >> 12) & 0x7
        piece_moved = (m >> 15) & 0x7
        captured = (m >> 18) & 0x7
        
        if promo != NONE:
            scores[i] = 9000000 + PIECE_VALUE[promo]
        elif captured != NONE:
            aggressor = piece_moved
            ag_val = PIECE_VALUE[aggressor]
            scores[i] = 8000000 + PIECE_VALUE[captured] * 10 - ag_val
        else:
            if m == killers[ply, 0]:
                scores[i] = 7000000
            elif m == killers[ply, 1]:
                scores[i] = 6000000
            else:
                scores[i] = history_table[fr, to]
    return scores

@njit(cache=False)
def insertion_sort(moves, scores, count):
    for i in range(1, count):
        key_move = moves[i]
        key_score = scores[i]
        j = i - 1
        while j >= 0 and scores[j] < key_score:
            scores[j + 1] = scores[j]
            moves[j + 1] = moves[j]
            j -= 1
        scores[j + 1] = key_score
        moves[j + 1] = key_move

@njit(cache=False)
def least_valuable_attacker(pieces, colors, occ, sq, side):
    own = colors[side] & occ
    bb = PAWN_ATTACKS[side ^ 1][sq] & pieces[PAWN] & own
    if bb:
        return lsb(bb), PAWN
    bb = KNIGHT_ATTACKS[sq] & pieces[KNIGHT] & own
    if bb:
        return lsb(bb), KNIGHT

    b_att = get_bishop_attacks(sq, occ)
    bb = b_att & pieces[BISHOP] & own
    if bb:
        return lsb(bb), BISHOP

    r_att = get_rook_attacks(sq, occ)
    bb = r_att & pieces[ROOK] & own
    if bb:
        return lsb(bb), ROOK

    q_att = b_att | r_att
    bb = q_att & pieces[QUEEN] & own
    if bb:
        return lsb(bb), QUEEN

    bb = KING_ATTACKS[sq] & pieces[KING] & own
    if bb:
        return lsb(bb), KING

    return -1, NONE

@njit(cache=False)
def see(pieces, colors, state, move):
    fr_sq = move & 0x3F
    to_sq = (move >> 6) & 0x3F
    promo = (move >> 12) & 0x7
    piece_moved = (move >> 15) & 0x7
    captured = (move >> 18) & 0x7
    is_ep = (move >> 21) & 1

    if captured == NONE or promo != NONE or is_ep:
        return 0

    gain = np.zeros(64, dtype=np.int32)
    occ = colors[WHITE] | colors[BLACK]
    side = np.int64(state[0])

    gain[0] = SEE_VALUE[captured]
    attacker = piece_moved
    occ ^= np.uint64(1) << np.uint64(fr_sq)

    d = 0
    while d < 62:
        d += 1
        side ^= 1
        gain[d] = SEE_VALUE[attacker] - gain[d - 1]
        if max(-gain[d - 1], gain[d]) < 0:
            break
        sq = -1
        piece = 0
        while True:
            sq, piece = least_valuable_attacker(pieces, colors, occ, to_sq, side)
            if sq < 0:
                break
            
            is_legal = True
            king_bb = pieces[KING] & colors[side]
            if king_bb:
                king_sq = lsb(king_bb)
                new_occ = occ ^ (np.uint64(1) << np.uint64(sq))
                opp = side ^ 1
                enemy_rooks = (pieces[ROOK] | pieces[QUEEN]) & colors[opp]
                enemy_bishops = (pieces[BISHOP] | pieces[QUEEN]) & colors[opp]
                if piece == KING:
                    if enemy_rooks and (get_rook_attacks(to_sq, new_occ) & enemy_rooks): is_legal = False
                    elif enemy_bishops and (get_bishop_attacks(to_sq, new_occ) & enemy_bishops): is_legal = False
                    elif side == WHITE and (PAWN_ATTACKS[BLACK][to_sq] & pieces[PAWN] & colors[BLACK]): is_legal = False
                    elif side == BLACK and (PAWN_ATTACKS[WHITE][to_sq] & pieces[PAWN] & colors[WHITE]): is_legal = False
                    elif KNIGHT_ATTACKS[to_sq] & pieces[KNIGHT] & colors[opp]: is_legal = False
                    elif KING_ATTACKS[to_sq] & pieces[KING] & colors[opp]: is_legal = False
                else:
                    if enemy_rooks and (get_rook_attacks(king_sq, new_occ) & enemy_rooks): is_legal = False
                    elif enemy_bishops and (get_bishop_attacks(king_sq, new_occ) & enemy_bishops): is_legal = False
            
            occ ^= np.uint64(1) << np.uint64(sq)
            if is_legal:
                break

        if sq < 0:
            break
        attacker = piece

    while d > 1:
        d -= 1
        gain[d - 1] = -max(-gain[d - 1], gain[d])

    return gain[0]

QS_KILLERS = np.zeros((1, 2), dtype=np.uint32)
QS_HISTORY = np.zeros((64, 64), dtype=np.int32)

@njit(cache=False)
def is_insufficient_material(pieces):
    if pieces[PAWN] or pieces[ROOK] or pieces[QUEEN]:
        return False
    knights = popcount(pieces[KNIGHT])
    bishops = popcount(pieces[BISHOP])
    return (knights + bishops) <= 1

@njit(cache=False)
def has_legal_moves(pieces, colors, state):
    moves = np.zeros(256, dtype=np.uint32)
    count = generate_pseudo_legal_moves(pieces, colors, state, moves)
    undo = np.zeros(4, dtype=np.uint64)
    for i in range(count):
        if make_move(pieces, colors, state, moves[i], undo):
            unmake_move(pieces, colors, state, moves[i], undo)
            return True
    return False

@njit(cache=False)
def qsearch(pieces, colors, state, alpha, beta, ply, path_keys, path_count, start_time, budget_ms, nodes, acc, diffs):
    nodes[0] += 1

    if (nodes[0] & 255) == 0:
        with objmode(curr_time='float64'):
            curr_time = time.time()
        if (curr_time - start_time) * 1000 > budget_ms * 0.85:
            nodes[1] = 1
            return alpha

    if ply >= 127:
        return pure_nnue_eval(pieces, colors, state, acc, weights_fc1, biases_fc1, weights_fc2, biases_fc2)
        
    if is_insufficient_material(pieces):
        return 0.0
        
    is_ch = in_check(pieces, colors, state)
    stand_pat = -1e9
    
    if not is_ch:
        stand_pat = pure_nnue_eval(pieces, colors, state, acc, weights_fc1, biases_fc1, weights_fc2, biases_fc2)
        if stand_pat >= beta:
            return stand_pat
        if alpha < stand_pat:
            alpha = stand_pat
            
    moves = np.zeros(256, dtype=np.uint32)
    count = generate_pseudo_legal_moves(pieces, colors, state, moves)
    
    if not is_ch:
        filtered_count = 0
        for i in range(count):
            m = moves[i]
            promo = (m >> 12) & 0x7
            captured = (m >> 18) & 0x7
            if promo != NONE or captured != NONE:
                moves[filtered_count] = m
                filtered_count += 1
        count = filtered_count
        
    if count == 0:
        return stand_pat

    scores = score_moves(moves, count, 0, QS_KILLERS, 0, QS_HISTORY)
    insertion_sort(moves, scores, count)
    
    best_score = -1e9 if is_ch else stand_pat
    undo = np.zeros(4, dtype=np.uint64)
    
    legal_moves_played = 0
    for i in range(count):
        move = moves[i]
        
        if not is_ch:
            promo = (move >> 12) & 0x7
            if promo == NONE:
                captured = (move >> 18) & 0x7
                victim = captured if captured != NONE else PAWN
                if stand_pat + PIECE_VALUE[victim] + 200 < alpha:
                    continue
                if captured != NONE and see(pieces, colors, state, move) < 0:
                    continue

        diff_count = extract_diffs(move, state[0], diffs[ply])
        apply_diffs(weights_acc, acc, diffs[ply], diff_count)
        is_legal = make_move(pieces, colors, state, move, undo)
        if not is_legal:
            unmake_move(pieces, colors, state, move, undo)
            for j in range(diff_count): diffs[ply, j, 0] = -diffs[ply, j, 0]
            apply_diffs(weights_acc, acc, diffs[ply], diff_count)
            continue
            
        legal_moves_played += 1
        child_score = -qsearch(pieces, colors, state, -beta, -alpha, ply + 1, path_keys, path_count, start_time, budget_ms, nodes, acc, diffs)
        unmake_move(pieces, colors, state, move, undo)
        for j in range(diff_count): diffs[ply, j, 0] = -diffs[ply, j, 0]
        apply_diffs(weights_acc, acc, diffs[ply], diff_count)

        if nodes[1] != 0:
            break

        if child_score > best_score:
            best_score = child_score
        if child_score > alpha:
            alpha = child_score
        if alpha >= beta:
            break
            
    if is_ch and legal_moves_played == 0:
        return float(-(MATE_VALUE - ply))
        
    return best_score

@njit(cache=False)
def negamax(pieces, colors, state, depth, ply, alpha, beta, prev_is_null, 
            path_keys, path_count, pos_counts_keys, pos_counts_vals, 
            killers, history_table, start_time, budget_ms, max_nodes, nodes, panic,
            tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, root_depth, acc, diffs):
    
    nodes[0] += 1
    if (nodes[0] & 255) == 0:
        with objmode(curr_time='float64'):
            curr_time = time.time()
        if (curr_time - start_time) * 1000 > budget_ms * 0.85:
            nodes[1] = 1
            return 0.0

    is_ch = in_check(pieces, colors, state)
    if is_ch and ply < 2 * root_depth:
        depth += 1

    if is_insufficient_material(pieces):
        return 0.0

    hash_key = state[4]
    
    if ply > 0:
        for i in range(len(pos_counts_keys)):
            if pos_counts_keys[i] == hash_key and pos_counts_vals[i] >= 2:
                return get_draw_score(ply)
                
    for i in range(path_count):
        if path_keys[i] == hash_key:
            return get_draw_score(ply)
            
    if state[3] >= 100:
        return get_draw_score(ply)
        
    tt_idx = hash_key % TT_SIZE
    tt_entry_key = tt_keys[tt_idx]
    tt_move = np.uint32(0)
    orig_alpha = alpha
    
    if tt_entry_key == hash_key:
        tt_depth = tt_depths[tt_idx]
        tt_score = tt_scores[tt_idx]
        tt_flag = tt_flags[tt_idx]
        tt_move = tt_moves[tt_idx]
        
        if tt_depth >= depth:
            score = float(tt_score)
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
                
    if depth <= 0:
        return qsearch(pieces, colors, state, alpha, beta, ply, path_keys, path_count, start_time, budget_ms, nodes, acc, diffs)
        
    path_keys[path_count] = hash_key
    path_count += 1
    
    if not is_ch and depth >= 3 and not prev_is_null:
        us_pieces = colors[state[0]]
        has_non_pawn = bool(us_pieces & (pieces[KNIGHT] | pieces[BISHOP] | pieces[ROOK] | pieces[QUEEN]))
        if has_non_pawn:
            opp = state[0] ^ 1
            ep_save = state[2]
            clock_save = state[3]
            hash_save = state[4]
            
            state[0] = opp
            state[2] = 64
            state[3] = clock_save + 1
            
            new_hash = hash_save ^ bitboard.ZOBRIST_TURN
            if ep_save != 64:
                new_hash ^= bitboard.ZOBRIST_EP[ep_save % 8]
            state[4] = new_hash
            
            null_score = -negamax(pieces, colors, state, depth - 3, ply + 1, -beta, -beta + 1, True, 
                                  path_keys, path_count, pos_counts_keys, pos_counts_vals,
                                  killers, history_table, start_time, budget_ms, max_nodes, nodes, panic,
                                  tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, root_depth, acc, diffs)
            
            state[0] = opp ^ 1
            state[2] = ep_save
            state[3] = clock_save
            state[4] = hash_save
            
            if null_score >= beta:
                path_count -= 1
                return null_score
                
    moves = np.zeros(256, dtype=np.uint32)
    count = generate_pseudo_legal_moves(pieces, colors, state, moves)
    
    scores = score_moves(moves, count, tt_move, killers, ply, history_table)
    insertion_sort(moves, scores, count)
    
    best_score = -1e9
    current_best_move = np.uint32(0)
    legal_moves_played = 0
    undo = np.zeros(4, dtype=np.uint64)
    
    for i in range(count):
        move = moves[i]
        is_capture = ((move >> 18) & 0x7) != NONE
        promo = (move >> 12) & 0x7
        is_quiet = not is_capture and promo == NONE and move != killers[ply, 0] and move != killers[ply, 1]
        
        diff_count = extract_diffs(move, state[0], diffs[ply])
        apply_diffs(weights_acc, acc, diffs[ply], diff_count)
        is_legal = make_move(pieces, colors, state, move, undo)
        if not is_legal:
            unmake_move(pieces, colors, state, move, undo)
            for j in range(diff_count): diffs[ply, j, 0] = -diffs[ply, j, 0]
            apply_diffs(weights_acc, acc, diffs[ply], diff_count)
            continue
            
        legal_moves_played += 1
        needs_full_search = True
        score = 0.0
        
        gives_check = in_check(pieces, colors, state)
        if legal_moves_played >= 4 and depth >= 3 and not is_ch and is_quiet and not gives_check:
            reduced_score = -negamax(pieces, colors, state, depth - 2, ply + 1, -alpha - 1, -alpha, False,
                                     path_keys, path_count, pos_counts_keys, pos_counts_vals,
                                     killers, history_table, start_time, budget_ms, max_nodes, nodes, panic,
                                     tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, root_depth, acc, diffs)
            if reduced_score > alpha:
                needs_full_search = True
            else:
                score = reduced_score
                needs_full_search = False
                
        if needs_full_search:
            score = -negamax(pieces, colors, state, depth - 1, ply + 1, -beta, -alpha, False,
                             path_keys, path_count, pos_counts_keys, pos_counts_vals,
                             killers, history_table, start_time, budget_ms, max_nodes, nodes, panic,
                             tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, root_depth, acc, diffs)
                             
        unmake_move(pieces, colors, state, move, undo)
        for j in range(diff_count): diffs[ply, j, 0] = -diffs[ply, j, 0]
        apply_diffs(weights_acc, acc, diffs[ply], diff_count)

        if nodes[1] != 0:
            path_count -= 1
            return 0.0
        
        if score > best_score:
            best_score = score
            current_best_move = move
            
        if score > alpha:
            alpha = score
            
        if alpha >= beta:
            if not is_capture:
                if move != killers[ply, 0]:
                    killers[ply, 1] = killers[ply, 0]
                    killers[ply, 0] = move
                fr = move & 0x3F
                to = (move >> 6) & 0x3F
                history_table[fr, to] += depth * depth
            break
            
    if legal_moves_played == 0:
        path_count -= 1
        if is_ch:
            return float(-(MATE_VALUE - ply))
        return 0.0
        
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
        
    if nodes[1] == 0:
        tt_keys[tt_idx] = hash_key
        tt_depths[tt_idx] = depth
        tt_scores[tt_idx] = store_score
        tt_flags[tt_idx] = flag
        tt_moves[tt_idx] = current_best_move
    
    path_count -= 1
    return best_score

@njit(cache=False)
def numba_search(pieces, colors, state, time_left_ms, pos_counts_keys, pos_counts_vals, max_nodes, start_time, 
                 tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, max_depth=64):
    acc = np.zeros((2, 256), dtype=np.int16)
    nnue_full_refresh(pieces, colors, weights_acc, biases_acc, acc)
    diffs = np.zeros((128, 6, 4), dtype=np.int8)

    if time_left_ms < 3000:
        budget_ms = min(time_left_ms * 0.15, 400.0)
        panic = True
    else:
        budget_ms = min(time_left_ms * 0.045 + 400.0, time_left_ms * 0.25)
        panic = False
        
    nodes = np.zeros(2, dtype=np.int64)
    killers = np.zeros((128, 2), dtype=np.uint32)
    history_table = np.zeros((64, 64), dtype=np.int32)
    path_keys = np.zeros(256, dtype=np.uint64)
    path_keys[0] = state[4]
    path_count = 1
    
    moves = np.zeros(256, dtype=np.uint32)
    count = generate_pseudo_legal_moves(pieces, colors, state, moves)
    
    legal_moves = np.zeros(256, dtype=np.uint32)
    legal_count = 0
    undo = np.zeros(4, dtype=np.uint64)
    for i in range(count):
        is_legal = make_move(pieces, colors, state, moves[i], undo)
        unmake_move(pieces, colors, state, moves[i], undo)
        if is_legal:
            legal_moves[legal_count] = moves[i]
            legal_count += 1
            
    if legal_count == 0:
        return 0, 0.0, 0, 0
        
    best_move = legal_moves[0]
    
    depth = 1
    completed_depth = 0
    prev_score = -1e9
    
    while depth <= max_depth:
        for i in range(legal_count):
            if legal_moves[i] == best_move:
                legal_moves[i] = legal_moves[0]
                legal_moves[0] = best_move
                break
                
        if depth >= 4 and abs(prev_score) < MATE_VALUE - 1000:
            alpha = prev_score - 30
            beta = prev_score + 30
            delta = 30
        else:
            alpha = -1e9
            beta = 1e9
            delta = 0
            
        while True:
            current_best_score = -1e9
            current_best_move = best_move
            
            for i in range(legal_count):
                move = legal_moves[i]
                diff_count = extract_diffs(move, state[0], diffs[0])
                apply_diffs(weights_acc, acc, diffs[0], diff_count)
                make_move(pieces, colors, state, move, undo)
                score = -negamax(pieces, colors, state, depth - 1, 1, -beta, -alpha, False,
                                 path_keys, path_count, pos_counts_keys, pos_counts_vals,
                                 killers, history_table, start_time, budget_ms, max_nodes, nodes, panic,
                                 tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, depth, acc, diffs)
                unmake_move(pieces, colors, state, move, undo)
                for j in range(diff_count): diffs[0, j, 0] = -diffs[0, j, 0]
                apply_diffs(weights_acc, acc, diffs[0], diff_count)
                
                # Check timeout
                timeout = False
                if nodes[1] != 0:
                    timeout = True
                elif max_nodes > 0 and nodes[0] >= max_nodes:
                    timeout = True
                else:
                    with objmode(curr_time='float64'):
                        curr_time = time.time()
                    if (curr_time - start_time) * 1000 > budget_ms * 0.85:
                        timeout = True
                    
                if timeout:
                    return best_move, prev_score, nodes[0], completed_depth
                    
                if score > current_best_score:
                    current_best_score = score
                    current_best_move = move
                    
                if score > alpha:
                    alpha = score
                    
                if alpha >= beta:
                    break
                    
            if delta > 0 and (current_best_score <= prev_score - delta or current_best_score >= beta):
                if delta == 30:
                    delta = 60
                    alpha = prev_score - delta
                    beta = prev_score + delta
                    continue
                else:
                    alpha = -1e9
                    beta = 1e9
                    delta = 0
                    continue
            break
            
        prev_score = current_best_score
        best_move = current_best_move
        completed_depth = depth

        if max_nodes > 0:
            if nodes[0] >= max_nodes / 2:
                break
        else:
            with objmode(curr_time='float64'):
                curr_time = time.time()
            if (curr_time - start_time) * 1000 > budget_ms / 2:
                break
                
        depth += 1
        
    return best_move, prev_score, nodes[0], completed_depth

def get_move_with_info(board: chess.Board, time_left_ms: int, position_counts, max_depth=64):
    pieces, colors, state = from_chess_board(board)
    
    pos_keys = []
    pos_vals = []
    for key, count in position_counts.items():
        if key is not None:
            pos_keys.append(key)
            pos_vals.append(count)
        
    pos_keys = np.array(pos_keys, dtype=np.uint64)
    pos_vals = np.array(pos_vals, dtype=np.int32)
    
    max_nodes_env = os.environ.get("SEARCH_MAX_NODES")
    max_nodes = int(max_nodes_env) if max_nodes_env else 0
    
    start_time = time.time()
    
    best_move, score, nodes, completed_depth = numba_search(
        pieces, colors, state, time_left_ms, pos_keys, pos_vals, max_nodes, start_time,
        tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, max_depth
    )
    
    if best_move == 0:
        return next(iter(board.legal_moves)).uci(), score, nodes
        
    uci = decode_move(best_move)
    if os.environ.get('CHESSATHON_DEPTH_LOG') == '1':
        print(f"info depth {completed_depth} score cp {int(score)} nodes {nodes}", file=sys.stderr)
    return uci, score, nodes

def get_move(board: chess.Board, time_left_ms: int, position_counts) -> str:
    uci, _, _ = get_move_with_info(board, time_left_ms, position_counts)
    return uci

# Warmup JIT compilation off the clock
print("Warming up Hybrid NNUE v2 + Classical Numba JIT...")
_b = chess.Board()
_p, _c, _s = from_chess_board(_b)
_pk = np.array([], dtype=np.uint64)
_pv = np.array([], dtype=np.int32)
clear_tt()
numba_search(_p, _c, _s, 1000, _pk, _pv, 10, time.time(), tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, 1)
print("Warmup complete.")
