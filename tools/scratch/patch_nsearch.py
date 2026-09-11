import re

with open('nsearch.py', 'r') as f:
    content = f.read()

# 1. Update imports
import_block = """from bitboard import (
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
    PAWN_ATTACKS,
    KNIGHT_ATTACKS,
    KING_ATTACKS,
    get_bishop_attacks,
    get_rook_attacks,
)"""
content = re.sub(r'from bitboard import \([\s\S]*?\)', import_block, content)

# 2. Insert see function before score_moves
see_func = """
@njit(cache=False)
def see(pieces, colors, state, move):
    fr = move & 0x3F
    to = (move >> 6) & 0x3F
    promo = (move >> 12) & 0x7
    piece_moved = (move >> 15) & 0x7
    captured = (move >> 18) & 0x7
    ep = (move >> 21) & 0x1
    
    if captured == NONE and promo == NONE:
        return 0
        
    piece_values = np.array([100, 320, 330, 500, 900, 100000, 0], dtype=np.int32)
    gain = np.zeros(32, dtype=np.int32)
    
    gain[0] = piece_values[captured]
    
    if promo != NONE:
        gain[0] += piece_values[promo] - piece_values[PAWN]
        piece_moved = promo
        
    current_piece = piece_moved
    d = 1
    
    blockers = colors[0] | colors[1]
    blockers ^= (np.uint64(1) << np.uint64(fr))
    
    if ep:
        if state[0] == 0:
            ep_sq = to - 8
        else:
            ep_sq = to + 8
        blockers ^= (np.uint64(1) << np.uint64(ep_sq))
        
    blockers |= (np.uint64(1) << np.uint64(to))
    
    side = state[0] ^ 1
    
    while True:
        attacker_piece = NONE
        attacker_sq = -1
        
        if side == 0:
            pawn_attackers = PAWN_ATTACKS[1][to] & pieces[PAWN] & colors[0] & blockers
        else:
            pawn_attackers = PAWN_ATTACKS[0][to] & pieces[PAWN] & colors[1] & blockers
            
        if pawn_attackers:
            attacker_piece = PAWN
            attacker_sq = lsb(pawn_attackers)
        else:
            knight_attackers = KNIGHT_ATTACKS[to] & pieces[KNIGHT] & colors[side] & blockers
            if knight_attackers:
                attacker_piece = KNIGHT
                attacker_sq = lsb(knight_attackers)
            else:
                bishop_attackers = get_bishop_attacks(to, blockers) & pieces[BISHOP] & colors[side] & blockers
                if bishop_attackers:
                    attacker_piece = BISHOP
                    attacker_sq = lsb(bishop_attackers)
                else:
                    rook_attackers = get_rook_attacks(to, blockers) & pieces[ROOK] & colors[side] & blockers
                    if rook_attackers:
                        attacker_piece = ROOK
                        attacker_sq = lsb(rook_attackers)
                    else:
                        queen_attackers = (get_bishop_attacks(to, blockers) | get_rook_attacks(to, blockers)) & pieces[QUEEN] & colors[side] & blockers
                        if queen_attackers:
                            attacker_piece = QUEEN
                            attacker_sq = lsb(queen_attackers)
                        else:
                            king_attackers = KING_ATTACKS[to] & pieces[KING] & colors[side] & blockers
                            if king_attackers:
                                attacker_piece = KING
                                attacker_sq = lsb(king_attackers)
                                
        if attacker_piece == NONE:
            break
            
        gain[d] = piece_values[current_piece]
        current_piece = attacker_piece
        blockers ^= (np.uint64(1) << np.uint64(attacker_sq))
        side ^= 1
        d += 1
        
    score = 0
    for i in range(d - 1, 0, -1):
        if gain[i] - score > 0:
            score = gain[i] - score
        else:
            score = 0
            
    return gain[0] - score

@njit(cache=False)
def score_moves"""

content = content.replace("@njit(cache=False)\ndef score_moves", see_func)

# 3. Update score_moves
old_score_moves = """        if m == tt_move:
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
                scores[i] = history_table[fr, to]"""

new_score_moves = """        if m == tt_move:
            scores[i] = 2000000000
            continue
            
        fr = m & 0x3F
        to = (m >> 6) & 0x3F
        promo = (m >> 12) & 0x7
        piece_moved = (m >> 15) & 0x7
        captured = (m >> 18) & 0x7
        
        if promo != NONE:
            scores[i] = 1900000000 + PIECE_VALUE[promo]
        elif captured != NONE:
            aggressor = piece_moved
            ag_val = PIECE_VALUE[aggressor]
            see_val = see(pieces, colors, state, m)
            if see_val >= 0:
                scores[i] = 1000000000 + see_val * 10000 + PIECE_VALUE[captured] * 10 - ag_val
            else:
                if see_val < -10000: see_val = -10000
                scores[i] = 700000000 + see_val * 10000 + PIECE_VALUE[captured] * 10 - ag_val
        else:
            if m == killers[ply, 0]:
                scores[i] = 900000000
            elif m == killers[ply, 1]:
                scores[i] = 800000000
            else:
                scores[i] = history_table[fr, to]"""
content = content.replace(old_score_moves, new_score_moves)

# 4. Update qsearch
old_qsearch = """        if not is_ch:
            promo = (move >> 12) & 0x7
            if promo == NONE:
                captured = (move >> 18) & 0x7
                victim = captured if captured != NONE else PAWN
                if stand_pat + PIECE_VALUE[victim] + 200 < alpha:
                    continue
                    
        is_legal = make_move"""

new_qsearch = """        if not is_ch:
            promo = (move >> 12) & 0x7
            if promo == NONE:
                captured = (move >> 18) & 0x7
                
                if captured != NONE and scores[i] < 800000000:
                    continue
                    
                victim = captured if captured != NONE else PAWN
                if stand_pat + PIECE_VALUE[victim] + 200 < alpha:
                    continue
                    
        is_legal = make_move"""
content = content.replace(old_qsearch, new_qsearch)

with open('nsearch.py', 'w') as f:
    f.write(content)

print("Patched nsearch.py successfully.")
