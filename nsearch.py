# ruff: noqa: E501
# mypy: ignore-errors
import math
import os
import time

import chess
import chess.syzygy
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

# SEE needs a king value: PIECE_VALUE has KING = 0, which would make the king look like
# a free attacker and invert the swap-off. 10000 keeps it last in the ordering, and a
# king capture into a still-defended square scores hugely negative, which is correct.
SEE_VALUE = np.array([100, 320, 330, 500, 900, 10000, 0], dtype=np.int32)

# Late move reduction depth, by (depth, move number). It was a flat 1 ply regardless of
# either, which under-reduces late moves at high depth. Built once at import so the
# search never calls log().
LMR_MAX = 64
LMR_TABLE = np.zeros((LMR_MAX, LMR_MAX), dtype=np.int32)
for _d in range(1, LMR_MAX):
    for _m in range(1, LMR_MAX):
        LMR_TABLE[_d, _m] = int(0.75 + math.log(_d) * math.log(_m) / 2.25)

# Bound on history_table entries. int32 with `depth * depth` bonuses reaches 4096 per
# update; a hot from/to pair over a long game can accumulate past int32 and wrap, which
# silently inverts move ordering. Clamping is cheaper than widening the table.
HISTORY_MAX = 32768
CONTEMPT = 0.0

# --- Syzygy root probe -------------------------------------------------------------
# Until v12 the 35 .rtbw files shipped in every submission and were never read:
# chess.syzygy was imported in search.py (the Python fallback) and nowhere else, and a
# runtime counter measured 0 probes on the numba path against 57,793 on the fallback.
#
# The probe lives here, at the Python entry point, and NEVER inside the search. It cannot
# go inside: chess.syzygy is not callable from njit code. It should not go inside either
# -- one probe per move costs 31-321 nodes against a ~2.5M nodes/sec search, but firing
# per node measured 41-303x slower.
#
# WDL alone would not have fixed anything. In the KBNvK position the engine shuffles in,
# all 21 legal moves score an identical 20000-ply under WDL: 1 distinct score against 4
# distinct DTZ values (-11, -9, -7, -3). DTZ is what makes the gradient exist, which is
# why v12 ships .rtbz as well.
TB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights")
TB_MAX_MEN = 4          # what weights/ actually covers
_tb = None
_tb_tried = False


def _tablebase():
    """Open the tablebase on first endgame, not at import.

    Deliberately lazy: python-chess opens the table files themselves lazily, and measuring
    cold import with and without the 35 .rtbz files showed no difference (11.2-11.5s vs
    11.5-11.8s). Init is already at ~34% of the 90s budget on the judge, so this stays
    off the import path regardless.
    """
    global _tb, _tb_tried
    if not _tb_tried:
        _tb_tried = True
        try:
            _tb = chess.syzygy.open_tablebase(TB_DIR)
        except Exception:
            _tb = None
    return _tb


def tb_root_move(board: chess.Board):
    """DTZ-optimal move when we are winning a position the tablebase covers, else None.

    Only intervenes when the root is a WIN for the side to move. Drawn and lost positions
    fall through to the search untouched -- there is nothing for DTZ to add there, and
    staying out keeps the blast radius small.

    Among children that are losing for the opponent, pick the smallest |DTZ|. DTZ is
    distance-to-zeroing, not distance-to-mate, so this is the move that makes progress
    against the fifty-move rule -- which is precisely what KBNvK needs.
    """
    if board.occupied.bit_count() > TB_MAX_MEN:
        return None
    tb = _tablebase()
    if tb is None:
        return None
    try:
        if tb.probe_wdl(board) <= 0:
            return None
    except Exception:
        return None

    best_move = None
    best_key = None
    for move in board.legal_moves:
        board.push(move)
        try:
            child_wdl = tb.probe_wdl(board)
            # A child that is a loss for the opponent is a win for us. Prefer an immediate
            # mate, then the smallest distance to a zeroing move.
            if board.is_checkmate():
                key = (-1, 0)
            elif child_wdl < 0:
                key = (0, abs(tb.probe_dtz(board)))
            else:
                key = None
        except Exception:
            key = None
        board.pop()
        if key is not None and (best_key is None or key < best_key):
            best_key, best_move = key, move
    return best_move



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
def least_valuable_attacker(pieces, colors, occ, sq, side):
    """Square and piece type of the cheapest `side` attacker of `sq`, given `occ`.

    Slider attacks are recomputed against the live occupancy every call. That is what
    makes x-rays work: once the front attacker is removed from `occ`, the slider behind
    it shows up here on the next iteration without any special case.

    Returns (-1, NONE) when `side` has no attacker left.
    """
    own = colors[side] & occ

    # PAWN_ATTACKS is indexed by the attacking side's *opposite*: the squares a `side`
    # pawn attacks sq from are the squares an opposing pawn on sq would attack.
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

    bb = (b_att | r_att) & pieces[QUEEN] & own
    if bb:
        return lsb(bb), QUEEN

    bb = KING_ATTACKS[sq] & pieces[KING] & own
    if bb:
        return lsb(bb), KING

    return -1, NONE


@njit(cache=False)
def see(pieces, colors, state, move):
    """Static exchange evaluation of a capture, in centipawns.

    Positive means the capture wins material once both sides have exchanged everything
    they profitably can on the target square. MVV-LVA cannot express this: it ranks QxP
    on a defended pawn by victim value alone, so quiescence searches it and burns nodes
    proving it was bad.

    Returns 0 for moves the swap-off does not model -- quiet moves, promotions (the
    moving piece changes value mid-exchange) and en passant (the captured pawn is not on
    the target square). Neutral rather than negative, so the SEE < 0 filter never skips
    them.
    """
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
        # Value of the piece now standing on to_sq, less what the previous side won.
        gain[d] = SEE_VALUE[attacker] - gain[d - 1]
        # Even conceding the piece outright cannot improve either side's result.
        if max(-gain[d - 1], gain[d]) < 0:
            break
        sq, piece = least_valuable_attacker(pieces, colors, occ, to_sq, side)
        if sq < 0:
            break
        occ ^= np.uint64(1) << np.uint64(sq)
        attacker = piece

    # Negamax back down the swap list: each side stands pat if capturing is worse.
    while d > 1:
        d -= 1
        gain[d - 1] = -max(-gain[d - 1], gain[d])

    return gain[0]


@njit(cache=False)
def qsearch(pieces, colors, state, alpha, beta, ply, path_keys, path_count, start_time, budget_ms, nodes):
    nodes[0] += 1

    # v11: quiescence used to take start_time and budget_ms and read neither, so a large
    # capture subtree ran past the deadline unchecked. Measured: 6,061 ms against a 648 ms
    # budget at ply 155, clock to -0.55 s, game lost on time. Same cadence and same
    # deadline negamax uses. nodes[1] is the shared stop flag; see numba_search.
    if (nodes[0] & 255) == 0:
        with objmode(curr_time='float64'):
            curr_time = time.time()
        if (curr_time - start_time) * 1000 > budget_ms * 0.85:
            nodes[1] = 1
            return alpha

    if ply >= 127:
        return evaluate(pieces, colors, state)
        
    is_ch = in_check(pieces, colors, state)
    stand_pat = -1e9
    
    if not is_ch:
        stand_pat = evaluate(pieces, colors, state)
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
                # v11: skip captures that lose material outright. MVV-LVA cannot tell a
                # winning capture from a losing one, so quiescence was searching QxP into
                # a defended pawn and burning nodes proving it was bad. Only when not in
                # check -- in check every evasion has to be searched.
                if captured != NONE and see(pieces, colors, state, move) < 0:
                    continue


        is_legal = make_move(pieces, colors, state, move, undo)
        if not is_legal:
            unmake_move(pieces, colors, state, move, undo)
            continue
            
        legal_moves_played += 1
        child_score = -qsearch(pieces, colors, state, -beta, -alpha, ply + 1, path_keys, path_count, start_time, budget_ms, nodes)
        unmake_move(pieces, colors, state, move, undo)

        # Same reason as in negamax: unwind immediately instead of starting the next
        # capture, and do not let the abort value become best_score.
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
            tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, root_depth):
    
    nodes[0] += 1
    if (nodes[0] & 255) == 0:
        with objmode(curr_time='float64'):
            curr_time = time.time()
        if (curr_time - start_time) * 1000 > budget_ms * 0.85:
            nodes[1] = 1  # v11: mark the search aborted so no TT entry is written
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
        return qsearch(pieces, colors, state, alpha, beta, ply, path_keys, path_count, start_time, budget_ms, nodes)
        
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
                                  tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, root_depth)
            
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

    # Quiets searched at this node, for the history penalty on a cutoff.
    quiet_moves = np.zeros(64, dtype=np.uint32)
    quiet_count = 0

    for i in range(count):
        move = moves[i]
        is_capture = ((move >> 18) & 0x7) != NONE
        promo = (move >> 12) & 0x7
        is_quiet = not is_capture and promo == NONE and move != killers[ply, 0] and move != killers[ply, 1]
        
        is_legal = make_move(pieces, colors, state, move, undo)
        if not is_legal:
            unmake_move(pieces, colors, state, move, undo)
            continue
            
        legal_moves_played += 1
        if is_quiet and quiet_count < 64:
            quiet_moves[quiet_count] = move
            quiet_count += 1
        needs_full_search = True
        score = 0.0
        
        gives_check = in_check(pieces, colors, state)
        if legal_moves_played >= 4 and depth >= 3 and not is_ch and is_quiet and not gives_check:
            # v11: reduction scales with depth and move number instead of a flat 1 ply.
            d_idx = depth if depth < LMR_MAX else LMR_MAX - 1
            m_idx = legal_moves_played if legal_moves_played < LMR_MAX else LMR_MAX - 1
            r = LMR_TABLE[d_idx, m_idx]
            if r < 1:
                r = 1
            reduced_depth = depth - 1 - r
            if reduced_depth < 1:
                reduced_depth = 1
            reduced_score = -negamax(pieces, colors, state, reduced_depth, ply + 1, -alpha - 1, -alpha, False,
                                     path_keys, path_count, pos_counts_keys, pos_counts_vals,
                                     killers, history_table, start_time, budget_ms, max_nodes, nodes, panic,
                                     tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, root_depth)
            if reduced_score > alpha:
                needs_full_search = True
            else:
                score = reduced_score
                needs_full_search = False
                
        if needs_full_search:
            score = -negamax(pieces, colors, state, depth - 1, ply + 1, -beta, -alpha, False,
                             path_keys, path_count, pos_counts_keys, pos_counts_vals,
                             killers, history_table, start_time, budget_ms, max_nodes, nodes, panic,
                             tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, root_depth)
                             
        unmake_move(pieces, colors, state, move, undo)

        # v11: stop the move loop the moment any descendant aborted on the deadline.
        # Checking only at node entry is not enough: an aborted child returns after ~256
        # nodes and the loop immediately starts the next one, so unwinding a depth-10
        # tree costs ~35 moves x 256 nodes per level. Measured 5.8M nodes and 1,951 ms
        # spent past the deadline before this check existed. `score` here is the
        # fabricated abort value, so break before it can become best_score.
        if nodes[1] != 0:
            break

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
                bonus = depth * depth
                fr = move & 0x3F
                to = (move >> 6) & 0x3F
                h = history_table[fr, to] + bonus
                if h > HISTORY_MAX:
                    h = HISTORY_MAX
                history_table[fr, to] = h
                # v11: penalise the quiets searched here that did not cut off. Rewarding
                # only the cutoff move leaves every quiet that failed at its old score,
                # so ordering never learns which ones are bad.
                for qi in range(quiet_count):
                    qm = quiet_moves[qi]
                    if qm == move:
                        continue
                    qf = qm & 0x3F
                    qt = (qm >> 6) & 0x3F
                    hq = history_table[qf, qt] - bonus
                    if hq < -HISTORY_MAX:
                        hq = -HISTORY_MAX
                    history_table[qf, qt] = hq
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
        
    # Always replace for now -- but never with the result of an aborted search.
    # v11: on timeout negamax returns a fabricated 0.0 which propagated up as a real
    # child score and was stored here as an exact entry. With "always replace" and the
    # table 98% full by move 156, every timed-out search poisoned it with fake draws.
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
    if time_left_ms < 3000:
        # v11: was min(200.0, time_left_ms * 0.1), which put a 2.7x cliff at the 3000 ms
        # boundary -- 535 ms of budget at 3000, 200 ms at 2999. 15% capped at 400 ms
        # keeps a large reserve while making the boundary nearly continuous. The search
        # still aborts at budget_ms * 0.85, so real spend here is ~340 ms at worst.
        budget_ms = min(time_left_ms * 0.15, 400.0)
        panic = True
    else:
        budget_ms = min(time_left_ms * 0.045 + 400.0, time_left_ms * 0.25)
        panic = False
        
    # nodes[0] = node count, nodes[1] = stop flag set when a search aborts on the
    # deadline. Carried in the existing array so no signature has to change.
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
                make_move(pieces, colors, state, move, undo)
                score = -negamax(pieces, colors, state, depth - 1, 1, -beta, -alpha, False,
                                 path_keys, path_count, pos_counts_keys, pos_counts_vals,
                                 killers, history_table, start_time, budget_ms, max_nodes, nodes, panic,
                                 tt_keys, tt_depths, tt_scores, tt_flags, tt_moves, depth)
                unmake_move(pieces, colors, state, move, undo)
                
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

        # v11: `if panic: break` used to sit here, stopping after one iteration and --
        # because it broke before `completed_depth = depth` below -- reporting depth 0
        # for every move under 3 s of clock. The engine spent 2.4 ms of a 200 ms budget
        # and played the first move iterative deepening happened to have.
        #
        # Removing it cannot cause a flag: the loop below only starts another iteration
        # while less than half the budget is gone, and every iteration aborts at
        # budget_ms * 0.85 like any other. It just stops discarding the budget.

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
    # v12: root Syzygy. Returns immediately on a tablebase win, so the search never runs
    # for those positions and the clock is untouched.
    tb_move = tb_root_move(board)
    if tb_move is not None:
        return tb_move.uci(), 0.0, 0

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


