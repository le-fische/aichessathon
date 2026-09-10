# ruff: noqa: E501
# mypy: ignore-errors
import time

import chess
import numpy as np
from numba import njit, objmode

# NNUE Setup
import os
import numpy as np

# Load weights relative to this file, from weights/, which is where
# tools/train_nnue.py writes them and where the packaged zip carries them.
# The previous version looked for root-level files in the process working
# directory. They were never there, so the fallback below ran every time and
# every NNUE gate measured an all-zero network.
_HERE = os.path.dirname(os.path.abspath(__file__))
_W = os.path.join(_HERE, "weights", "weights.npy")
if os.path.exists(_W):
    weights = np.load(_W)
    biases = np.load(os.path.join(_HERE, "weights", "biases.npy"))
    weights2 = np.load(os.path.join(_HERE, "weights", "weights2.npy"))
else:
    weights = np.zeros((768, 256), dtype=np.int16)
    biases = np.zeros(256, dtype=np.int16)
    weights2 = np.zeros(512, dtype=np.int8)

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
    diffs[count, 0] = -1; diffs[count, 1] = turn; diffs[count, 2] = piece_moved; diffs[count, 3] = fr; count += 1
    diffs[count, 0] = 1; diffs[count, 1] = turn; diffs[count, 2] = promo if promo != 6 else piece_moved; diffs[count, 3] = to; count += 1
    if captured != 6:
        cap_sq = to
        if ep:
            cap_sq = to - 8 if turn == 0 else to + 8
        diffs[count, 0] = -1; diffs[count, 1] = opp; diffs[count, 2] = 0 if ep else captured; diffs[count, 3] = cap_sq; count += 1
    if castle:
        if to == 62:  # g8, Black kingside: rook h8 -> f8
            diffs[count, 0] = -1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 63; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 61; count+=1
        elif to == 58:  # c8, Black queenside: rook a8 -> d8
            diffs[count, 0] = -1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 56; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 59; count+=1
        elif to == 6:  # g1, White kingside: rook h1 -> f1
            diffs[count, 0] = -1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 7; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 5; count+=1
        elif to == 2:  # c1, White queenside: rook a1 -> d1
            diffs[count, 0] = -1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 0; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 3; count+=1
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

@njit(cache=False)
def nnue_eval(weights2, acc, turn):
    out = 0
    opp = turn ^ 1
    for i in range(256):
        v = acc[turn, i]
        if v < 0: v = 0
        elif v > 127: v = 127
        out += v * weights2[i]
    for i in range(256):
        v = acc[opp, i]
        if v < 0: v = 0
        elif v > 127: v = 127
        out += v * weights2[256 + i]
    return out // 64


import bitboard
from bitboard import (
    BISHOP,
    KING,
    KNIGHT,
    NONE,
    PAWN,
    QUEEN,
    ROOK,
    decode_move,
    evaluate,
    from_chess_board,
    generate_pseudo_legal_moves,
    is_square_attacked,
    lsb,
    make_move,
    unmake_move,
)

# Constants
TT_EXACT = 0
TT_LOWER = 1
TT_UPPER = 2
MATE_VALUE = 30000

# TT Arrays
TT_SIZE = 16777216  # 2^24
tt_keys = np.zeros(TT_SIZE, dtype=np.uint64)
tt_depths = np.zeros(TT_SIZE, dtype=np.int8)
tt_scores = np.zeros(TT_SIZE, dtype=np.float32)
tt_flags = np.zeros(TT_SIZE, dtype=np.uint8)
tt_moves = np.zeros(TT_SIZE, dtype=np.uint32)

PIECE_VALUE = np.array([100, 320, 330, 500, 900, 0, 0], dtype=np.int32)
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
    king_sq = -1
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
def qsearch(pieces, colors, state, alpha, beta, ply, path_keys, path_count, start_time, budget_ms, nodes, acc, diffs):
    nodes[0] += 1
    
    if ply >= 127:
        return nnue_eval(weights2, acc, state[0])
        
    is_ch = in_check(pieces, colors, state)
    stand_pat = -1e9
    
    if not is_ch:
        stand_pat = nnue_eval(weights2, acc, state[0])
        if stand_pat >= beta:
            return stand_pat
        if alpha < stand_pat:
            alpha = stand_pat
            
    moves = np.zeros(256, dtype=np.uint32)
    count = generate_pseudo_legal_moves(pieces, colors, state, moves)
    
    # Filter captures and promotions if not in check
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
        if is_ch:
            # We don't know if checkmate because pseudo moves might all be illegal
            # But qsearch usually evaluates after legal checks
            # In qsearch if no legal captures we just return stand_pat if not in check
            # Wait, if in check we need legal moves.
            pass
        return stand_pat

    # Fake killers and history for qsearch score
    killers = np.zeros((1, 2), dtype=np.uint32)
    history = np.zeros((64, 64), dtype=np.int32)
    scores = score_moves(moves, count, 0, killers, 0, history)
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
                    
        diff_count = extract_diffs(move, state[0], diffs)
        apply_diffs(weights, acc, diffs, diff_count)
        is_legal = make_move(pieces, colors, state, move, undo)
        if not is_legal:
            unmake_move(pieces, colors, state, move, undo)
            for j in range(diff_count): diffs[j, 0] = -diffs[j, 0]
            apply_diffs(weights, acc, diffs, diff_count)
            continue
            
        legal_moves_played += 1
        child_score = -qsearch(pieces, colors, state, -beta, -alpha, ply + 1, path_keys, path_count, start_time, budget_ms, nodes, acc, diffs)
        unmake_move(pieces, colors, state, move, undo)
        for j in range(diff_count): diffs[j, 0] = -diffs[j, 0]
        apply_diffs(weights, acc, diffs, diff_count)
        
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
            return 0.0 # Timeout
    is_ch = in_check(pieces, colors, state)
    if is_ch and ply < 2 * root_depth:
        depth += 1


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
    
    is_ch = in_check(pieces, colors, state)
    
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
        
        diff_count = extract_diffs(move, state[0], diffs)
        apply_diffs(weights, acc, diffs, diff_count)
        is_legal = make_move(pieces, colors, state, move, undo)
        if not is_legal:
            unmake_move(pieces, colors, state, move, undo)
            for j in range(diff_count): diffs[j, 0] = -diffs[j, 0]
            apply_diffs(weights, acc, diffs, diff_count)
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
        for j in range(diff_count): diffs[j, 0] = -diffs[j, 0]
        apply_diffs(weights, acc, diffs, diff_count)
        
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
        
    # Always replace for now
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
    nnue_full_refresh(pieces, colors, weights, biases, acc)
    diffs = np.zeros((6, 4), dtype=np.int8)
    if time_left_ms < 3000:
        budget_ms = min(200.0, time_left_ms * 0.1)
        panic = True
    else:
        budget_ms = min(time_left_ms * 0.045 + 400.0, time_left_ms * 0.25)
        panic = False
        
    nodes = np.zeros(1, dtype=np.int64)
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
                diff_count = extract_diffs(move, state[0], diffs)
                apply_diffs(weights, acc, diffs, diff_count)
                make_move(pieces, colors, state, move, undo)
                score = -negamax(pieces, colors, state, depth - 1, 1, -beta, -alpha, False,
                                 path_keys, path_count, pos_counts_keys, pos_counts_vals,
                                 killers, history_table, start_time, budget_ms, max_nodes, nodes, panic,
                                 tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, depth, acc, diffs)
                unmake_move(pieces, colors, state, move, undo)
                for j in range(diff_count): diffs[j, 0] = -diffs[j, 0]
                apply_diffs(weights, acc, diffs, diff_count)
                
                # Check timeout
                timeout = False
                if max_nodes > 0 and nodes[0] >= max_nodes:
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
        
        if panic:
            break
                    
        if max_nodes > 0:
            if nodes[0] >= max_nodes / 2:
                break
        else:
            with objmode(curr_time='float64'):
                curr_time = time.time()
            if (curr_time - start_time) * 1000 > budget_ms / 2:
                break
                
        completed_depth = depth
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
    
    import os
    max_nodes_env = os.environ.get("SEARCH_MAX_NODES")
    max_nodes = int(max_nodes_env) if max_nodes_env else 0
    
    start_time = time.time()
    
    best_move, score, nodes, completed_depth = numba_search(pieces, colors, state, time_left_ms, pos_keys, pos_vals, max_nodes, start_time,
                                           tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, max_depth)
    
    if best_move == 0:
        return next(iter(board.legal_moves)).uci(), score, nodes
        
    uci = decode_move(best_move)
    import sys
    import os
    if os.environ.get('CHESSATHON_DEPTH_LOG') == '1':
        print(f"info depth {completed_depth} score cp {int(score)} nodes {nodes}", file=sys.stderr)
    return uci, score, nodes

def get_move(board: chess.Board, time_left_ms: int, position_counts) -> str:
    uci, _, _ = get_move_with_info(board, time_left_ms, position_counts)
    return uci

# Warmup JIT compilation off the clock
print("Warming up Numba JIT...")
_b = chess.Board()
_p, _c, _s = from_chess_board(_b)
_pk = np.array([], dtype=np.uint64)
_pv = np.array([], dtype=np.int32)
clear_tt()
numba_search(_p, _c, _s, 1000, _pk, _pv, 10, time.time(), tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, 1)
print("Warmup complete.")


