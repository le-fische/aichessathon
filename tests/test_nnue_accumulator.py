import random
import numpy as np
import chess
from numba import njit
import sys

sys.path.append('.')
import bitboard

# We pull in the exact Numba accumulator logic we intend to use.
# Since it's in bench_nnue_forward / nsearch_nnue right now, I'll define it here to test it cleanly.
@njit(cache=True)
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

@njit(cache=True)
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
    diffs[count, 0] = -1
    diffs[count, 1] = turn
    diffs[count, 2] = piece_moved
    diffs[count, 3] = fr
    count += 1
    
    diffs[count, 0] = 1
    diffs[count, 1] = turn
    diffs[count, 2] = promo if promo != 6 else piece_moved
    diffs[count, 3] = to
    count += 1
    
    if captured != 6:
        cap_sq = to
        if ep:
            cap_sq = to - 8 if turn == 0 else to + 8
        diffs[count, 0] = -1
        diffs[count, 1] = opp
        diffs[count, 2] = 0 if ep else captured
        diffs[count, 3] = cap_sq
        count += 1
        
    if castle:
        if to == 6: # wks
            diffs[count, 0] = -1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 7; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 5; count+=1
        elif to == 2: # wqs
            diffs[count, 0] = -1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 0; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 3; count+=1
        elif to == 62: # bks
            diffs[count, 0] = -1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 63; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 61; count+=1
        elif to == 58: # bqs
            diffs[count, 0] = -1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 56; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 59; count+=1
            
    return count

@njit(cache=True)
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

def test_accumulator_equivalence():
    np.random.seed(42)
    weights = np.random.randint(-127, 127, size=(768, 256), dtype=np.int16)
    biases = np.random.randint(-127, 127, size=(256,), dtype=np.int16)
    
    print("Running Numba accumulator equivalence test over random walks...")
    diffs_buf = np.zeros((6, 4), dtype=np.int8)
    
    # 50 random games
    for game_idx in range(50):
        board = chess.Board()
        p, c, s = bitboard.from_chess_board(board)
        
        acc = np.zeros((2, 256), dtype=np.int16)
        nnue_full_refresh(p, c, weights, biases, acc)
        
        move_history = []
        undo_history = []
        
        # Play up to 150 random moves or until game over
        for i in range(150):
            moves = np.zeros(256, dtype=np.uint32)
            count = bitboard.generate_pseudo_legal_moves(p, c, s, moves)
            
            legal_moves = []
            undos = []
            for j in range(count):
                m = moves[j]
                u = np.zeros(4, dtype=np.uint64)
                if bitboard.make_move(p, c, s, m, u):
                    legal_moves.append(m)
                    undos.append(u)
                bitboard.unmake_move(p, c, s, m, u)
                
            if not legal_moves:
                break
                
            choice_idx = random.randint(0, len(legal_moves) - 1)
            move = legal_moves[choice_idx]
            u = undos[choice_idx]
            
            # Incremental update BEFORE make_move (using current turn)
            diff_count = extract_diffs(move, s[0], diffs_buf)
            apply_diffs(weights, acc, diffs_buf, diff_count)
            
            bitboard.make_move(p, c, s, move, u)
            
            move_history.append(move)
            undo_history.append((u, diff_count, diffs_buf.copy()))
            
            # Full refresh for equivalence check
            ref_acc = np.zeros((2, 256), dtype=np.int16)
            nnue_full_refresh(p, c, weights, biases, ref_acc)
            
            np.testing.assert_array_equal(acc, ref_acc, err_msg=f"Game {game_idx}, ply {i}: Accumulator mismatch after make_move")
            
        # Unmake the moves and verify again
        for i in reversed(range(len(move_history))):
            move = move_history[i]
            u, diff_count, step_diffs = undo_history[i]
            
            bitboard.unmake_move(p, c, s, move, u)
            
            # Incremental unmake: invert diff signs
            for j in range(diff_count):
                step_diffs[j, 0] = -step_diffs[j, 0]
            apply_diffs(weights, acc, step_diffs, diff_count)
            
            ref_acc = np.zeros((2, 256), dtype=np.int16)
            nnue_full_refresh(p, c, weights, biases, ref_acc)
            
            np.testing.assert_array_equal(acc, ref_acc, err_msg=f"Game {game_idx}, POP ply {i}: Accumulator mismatch after unmake_move")

    print("Accumulator Equivalence Test: PASSED. All Numba incremental updates exactly match from-scratch recomputation for 50 random games (make and unmake).")

if __name__ == "__main__":
    test_accumulator_equivalence()
