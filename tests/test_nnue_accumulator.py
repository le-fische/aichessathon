import chess
import numpy as np
import random
from nnue import NNUEBoard, NNUEAccumulator

def test_accumulator_equivalence():
    # Random weights (256, 768) and biases (256)
    weights = np.random.randint(-127, 127, size=(256, 768), dtype=np.int16)
    biases = np.random.randint(-127, 127, size=(256,), dtype=np.int16)
    
    # 50 random games
    for game_idx in range(50):
        board = NNUEBoard(accumulator_weights=weights, accumulator_biases=biases)
        
        # Recomputed accumulator reference
        ref_acc = NNUEAccumulator(weights, biases)
        
        move_history = []
        
        # Play up to 100 random moves or until game over
        for i in range(100):
            if board.is_game_over():
                break
                
            legal_moves = list(board.legal_moves)
            move = random.choice(legal_moves)
            
            # Make the move
            board.push(move)
            move_history.append(move)
            
            # Recompute from scratch on a normal chess.Board (to be completely independent)
            plain_board = chess.Board(board.fen())
            ref_acc.init_from_board(plain_board)
            
            # Verify equivalence
            np.testing.assert_array_equal(board.accumulator.white_acc, ref_acc.white_acc, err_msg=f"Game {game_idx}, ply {i}: White accumulator mismatch after move {move}")
            np.testing.assert_array_equal(board.accumulator.black_acc, ref_acc.black_acc, err_msg=f"Game {game_idx}, ply {i}: Black accumulator mismatch after move {move}")
            
        # Unmake the moves and verify again
        for i in reversed(range(len(move_history))):
            move = board.pop()
            
            plain_board = chess.Board(board.fen())
            ref_acc.init_from_board(plain_board)
            
            np.testing.assert_array_equal(board.accumulator.white_acc, ref_acc.white_acc, err_msg=f"Game {game_idx}, POP ply {i}: White accumulator mismatch after pop {move}")
            np.testing.assert_array_equal(board.accumulator.black_acc, ref_acc.black_acc, err_msg=f"Game {game_idx}, POP ply {i}: Black accumulator mismatch after pop {move}")

    print("Accumulator Equivalence Test: PASSED. All incremental updates exactly match from-scratch recomputation for 50 random games (push and pop).")

if __name__ == "__main__":
    test_accumulator_equivalence()
