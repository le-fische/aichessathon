import sys
import chess
import collections
import numpy as np

from nsearch import from_chess_board, SEE_VALUE, least_valuable_attacker, KING, ROOK, QUEEN, BISHOP, PAWN, KNIGHT, WHITE, BLACK, PAWN_ATTACKS, KNIGHT_ATTACKS, KING_ATTACKS
from bitboard import get_rook_attacks, get_bishop_attacks, lsb

def see_trace(pieces, colors, state, move):
    fr_sq = move & 0x3F
    to_sq = (move >> 6) & 0x3F
    promo = (move >> 12) & 0x7
    piece_moved = (move >> 15) & 0x7
    captured = (move >> 18) & 0x7
    is_ep = (move >> 21) & 1

    print(f"captured={captured}, promo={promo}, is_ep={is_ep}")
    
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
        print(f"d={d}, side={side}, attacker={attacker}, gain[{d}]={gain[d]}")
        if max(-gain[d - 1], gain[d]) < 0:
            print("Break due to max(-gain...) < 0")
            break
        
        sq = -1
        piece = 0
        while True:
            sq, piece = least_valuable_attacker(pieces, colors, occ, to_sq, side)
            print(f"Least valuable attacker: sq={sq}, piece={piece}")
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
                    pass
                else:
                    if enemy_rooks and (get_rook_attacks(king_sq, new_occ) & enemy_rooks): is_legal = False
                    elif enemy_bishops and (get_bishop_attacks(king_sq, new_occ) & enemy_bishops): is_legal = False
            print(f"is_legal: {is_legal}")
            occ ^= np.uint64(1) << np.uint64(sq)
            if is_legal:
                break
                
        if sq < 0:
            break
        attacker = piece

    while d > 1:
        d -= 1
        gain[d - 1] = -max(-gain[d - 1], gain[d])
        print(f"backtrack d={d}, gain[{d-1}]={gain[d-1]}")

    return gain[0]

fen = "4k3/8/8/3pr3/8/8/8/3QR1K1 w - - 0 1"
board = chess.Board(fen)
pieces, colors, state = from_chess_board(board)
move = (3) | (35 << 6) | (0 << 18) | (4 << 15)
print("Score:", see_trace(pieces, colors, state, move))
