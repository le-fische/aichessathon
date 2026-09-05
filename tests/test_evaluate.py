import os
import sys

import chess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bitboard
import evaluation

# 6 Positions
FENS = [
    chess.STARTING_FEN,
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8",
    "r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6",
    "rnbq1rk1/pp2bppp/4pn2/2pp4/2PP4/N4NP1/PP2PPBP/R1BQK2R w KQ - 0 7",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
]

def test_eval():
    bitboard.warmup()
    
    any_failed = False
    for fen in FENS:
        board = chess.Board(fen)
        
        # Current evaluate
        expected = evaluation.evaluate(board)
        
        # Numba evaluate
        pieces, colors, state = bitboard.from_chess_board(board)
        actual = bitboard.evaluate(pieces, colors, state)
        
        if expected != actual:
            print(f"MISMATCH for FEN: {fen}")
            print(f"Expected: {expected}, Actual: {actual}")
            any_failed = True
        else:
            print(f"MATCH: {expected} == {actual} for FEN: {fen}")
            
    if any_failed:
        sys.exit(1)
        
if __name__ == "__main__":
    test_eval()
