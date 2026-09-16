import sys

import chess

sys.path.insert(0, '.')
import numpy as np

import bitboard


def verify_zobrist(pieces, colors, state, depth):
    computed = bitboard.compute_zobrist(pieces, colors, state)
    if state[4] != computed:
        return False
    if depth == 0:
        return True
        
    moves = np.zeros(256, dtype=np.uint32)
    count = bitboard.generate_pseudo_legal_moves(pieces, colors, state, moves)
    undo = np.zeros(4, dtype=np.uint64)
    
    for i in range(count):
        m = moves[i]
        old_hash = state[4]
        legal = bitboard.make_move(pieces, colors, state, m, undo)
        if legal and not verify_zobrist(pieces, colors, state, depth - 1):
            return False
        bitboard.unmake_move(pieces, colors, state, m, undo)
        if state[4] != old_hash:
            return False
            
    return True

def test_zobrist():
    # standard pos
    board = chess.Board()
    pieces, colors, state = bitboard.from_chess_board(board)
    assert verify_zobrist(pieces, colors, state, 3)
    
    # kiwipete
    board = chess.Board("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
    pieces, colors, state = bitboard.from_chess_board(board)
    assert verify_zobrist(pieces, colors, state, 2)
    
    print("Zobrist deep OK")

if __name__ == '__main__':
    test_zobrist()
