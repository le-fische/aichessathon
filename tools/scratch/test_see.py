from bitboard import get_rook_attacks, get_bishop_attacks, PAWN_ATTACKS, KNIGHT_ATTACKS
import numpy as np

def is_legal_see_move(king_sq, sq, to_sq, piece, side, pieces, colors, new_occ):
    # If king moved, check if to_sq is attacked
    # If not king, check if king_sq is attacked by slider
    opp = side ^ 1
    if piece == 5: # KING
        # king moved to to_sq
        king_sq = to_sq
        # check all attacks on king_sq
        if PAWN_ATTACKS[side][king_sq] & pieces[0] & colors[opp]: return False
        if KNIGHT_ATTACKS[king_sq] & pieces[1] & colors[opp]: return False
        
    # sliders
    enemy_rooks = (pieces[3] | pieces[4]) & colors[opp]
    enemy_bishops = (pieces[2] | pieces[4]) & colors[opp]
    
    if enemy_rooks:
        if get_rook_attacks(king_sq, new_occ) & enemy_rooks: return False
    if enemy_bishops:
        if get_bishop_attacks(king_sq, new_occ) & enemy_bishops: return False
        
    return True
