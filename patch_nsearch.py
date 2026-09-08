import re

with open("nsearch.py", "r") as f:
    code = f.read()

# Add the NNUE arrays to the top
header = """
# NNUE Setup
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
        if to == 62:
            diffs[count, 0] = -1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 63; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 61; count+=1
        elif to == 58:
            diffs[count, 0] = -1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 56; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 59; count+=1
        elif to == 6:
            diffs[count, 0] = -1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 7; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 5; count+=1
        elif to == 2:
            diffs[count, 0] = -1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 0; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 3; count+=1
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
    return out
"""

# Replace evaluate() calls
code = code.replace("evaluate(pieces, colors, state)", "nnue_eval(weights2, acc, state[0])")

# Add acc argument to qsearch
code = code.replace(
    "def qsearch(pieces, colors, state, alpha, beta, ply, path_keys, path_count, start_time, budget_ms, nodes):",
    "def qsearch(pieces, colors, state, alpha, beta, ply, path_keys, path_count, start_time, budget_ms, nodes, acc, diffs):"
)
code = code.replace(
    "qsearch(pieces, colors, state, -beta, -alpha, ply + 1, path_keys, path_count, start_time, budget_ms, nodes)",
    "qsearch(pieces, colors, state, -beta, -alpha, ply + 1, path_keys, path_count, start_time, budget_ms, nodes, acc, diffs)"
)

# Add acc argument to negamax
code = code.replace(
    "def negamax(pieces, colors, state, depth, ply, alpha, beta, prev_is_null, \n            path_keys, path_count, pos_counts_keys, pos_counts_vals, \n            killers, history_table, start_time, budget_ms, max_nodes, nodes, panic,\n            tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, root_depth):",
    "def negamax(pieces, colors, state, depth, ply, alpha, beta, prev_is_null, \n            path_keys, path_count, pos_counts_keys, pos_counts_vals, \n            killers, history_table, start_time, budget_ms, max_nodes, nodes, panic,\n            tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, root_depth, acc, diffs):"
)
code = code.replace(
    "negamax(pieces, colors, state, depth - 3, ply + 1, -beta, -beta + 1, True, \n                                  path_keys, path_count, pos_counts_keys, pos_counts_vals,\n                                  killers, history_table, start_time, budget_ms, max_nodes, nodes, panic,\n                                  tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, root_depth)",
    "negamax(pieces, colors, state, depth - 3, ply + 1, -beta, -beta + 1, True, \n                                  path_keys, path_count, pos_counts_keys, pos_counts_vals,\n                                  killers, history_table, start_time, budget_ms, max_nodes, nodes, panic,\n                                  tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, root_depth, acc, diffs)"
)
code = code.replace(
    "negamax(pieces, colors, state, depth - 2, ply + 1, -alpha - 1, -alpha, False,\n                                     path_keys, path_count, pos_counts_keys, pos_counts_vals,\n                                     killers, history_table, start_time, budget_ms, max_nodes, nodes, panic,\n                                     tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, root_depth)",
    "negamax(pieces, colors, state, depth - 2, ply + 1, -alpha - 1, -alpha, False,\n                                     path_keys, path_count, pos_counts_keys, pos_counts_vals,\n                                     killers, history_table, start_time, budget_ms, max_nodes, nodes, panic,\n                                     tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, root_depth, acc, diffs)"
)
code = code.replace(
    "negamax(pieces, colors, state, depth - 1, ply + 1, -beta, -alpha, False,\n                             path_keys, path_count, pos_counts_keys, pos_counts_vals,\n                             killers, history_table, start_time, budget_ms, max_nodes, nodes, panic,\n                             tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, root_depth)",
    "negamax(pieces, colors, state, depth - 1, ply + 1, -beta, -alpha, False,\n                             path_keys, path_count, pos_counts_keys, pos_counts_vals,\n                             killers, history_table, start_time, budget_ms, max_nodes, nodes, panic,\n                             tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, root_depth, acc, diffs)"
)

# Now, intercept make_move/unmake_move in qsearch and negamax!
# For qsearch:
code = code.replace(
    """        is_legal = make_move(pieces, colors, state, move, undo)
        if not is_legal:
            unmake_move(pieces, colors, state, move, undo)
            continue
            
        legal_moves_played += 1
        child_score = -qsearch(pieces, colors, state, -beta, -alpha, ply + 1, path_keys, path_count, start_time, budget_ms, nodes, acc, diffs)
        unmake_move(pieces, colors, state, move, undo)""",
    """        diff_count = extract_diffs(move, state[0], diffs)
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
        apply_diffs(weights, acc, diffs, diff_count)"""
)

# For negamax (same logic, there are two make_moves? Only one in loop!)
code = code.replace(
    """        is_legal = make_move(pieces, colors, state, move, undo)
        if not is_legal:
            unmake_move(pieces, colors, state, move, undo)
            continue""",
    """        diff_count = extract_diffs(move, state[0], diffs)
        apply_diffs(weights, acc, diffs, diff_count)
        is_legal = make_move(pieces, colors, state, move, undo)
        if not is_legal:
            unmake_move(pieces, colors, state, move, undo)
            for j in range(diff_count): diffs[j, 0] = -diffs[j, 0]
            apply_diffs(weights, acc, diffs, diff_count)
            continue"""
)
code = code.replace(
    """        unmake_move(pieces, colors, state, move, undo)
        
        if score > best_score:""",
    """        unmake_move(pieces, colors, state, move, undo)
        for j in range(diff_count): diffs[j, 0] = -diffs[j, 0]
        apply_diffs(weights, acc, diffs, diff_count)
        
        if score > best_score:"""
)

# Add acc array in numba_search
code = code.replace(
    "def numba_search(pieces, colors, state, time_left_ms, pos_counts_keys, pos_counts_vals, max_nodes, start_time, \n                 tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, max_depth=64):",
    "def numba_search(pieces, colors, state, time_left_ms, pos_counts_keys, pos_counts_vals, max_nodes, start_time, \n                 tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, max_depth=64):\n    acc = np.zeros((2, 256), dtype=np.int16)\n    nnue_full_refresh(pieces, colors, weights, biases, acc)\n    diffs = np.zeros((6, 4), dtype=np.int8)"
)

# And inside numba_search, we also need to apply diffs!
code = code.replace(
    """            for i in range(legal_count):
                move = legal_moves[i]
                make_move(pieces, colors, state, move, undo)
                score = -negamax(pieces, colors, state, depth - 1, 1, -beta, -alpha, False,
                                 path_keys, path_count, pos_counts_keys, pos_counts_vals,
                                 killers, history_table, start_time, budget_ms, max_nodes, nodes, panic,
                                 tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, depth)
                unmake_move(pieces, colors, state, move, undo)""",
    """            for i in range(legal_count):
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
                apply_diffs(weights, acc, diffs, diff_count)"""
)

# And finally the root warmup
code = code.replace(
    "numba_search(_p, _c, _s, 1000, _pk, _pv, 10, time.time(), tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, 1)",
    "numba_search(_p, _c, _s, 1000, _pk, _pv, 10, time.time(), tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, 1)"
)

code = code.replace("from numba import njit, objmode", "from numba import njit, objmode\n" + header)

with open("nsearch_nnue.py", "w") as f:
    f.write(code)
code = code.replace(
    "qsearch(pieces, colors, state, alpha, beta, ply, path_keys, path_count, start_time, budget_ms, nodes)",
    "qsearch(pieces, colors, state, alpha, beta, ply, path_keys, path_count, start_time, budget_ms, nodes, acc, diffs)"
)
with open("nsearch_nnue.py", "w") as f:
    f.write(code)
