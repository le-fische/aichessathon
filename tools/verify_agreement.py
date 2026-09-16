import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import random
import chess
import evaluation
import bitboard
from nsearch import from_chess_board

def main():
    random.seed(42)
    b = chess.Board()
    checked = 0
    for _ in range(5000):
        if b.is_game_over(claim_draw=False):
            b.reset()
            continue
            
        py_eval = evaluation.evaluate(b)
        pieces, colors, state = from_chess_board(b)
        nb_eval = bitboard.evaluate(pieces, colors, state)
        
        if py_eval != nb_eval:
            print(f"Divergence found! FEN: {b.fen()}")
            print(f"evaluation.py: {py_eval}")
            print(f"bitboard.py: {nb_eval}")
            sys.exit(1)
            
        b.push(random.choice(list(b.legal_moves)))
        checked += 1
        
    print(f"Agreement OK! Checked {checked} positions.")

if __name__ == "__main__":
    main()
