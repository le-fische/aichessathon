import time
import numpy as np
import chess
import sys
from numba import njit, types
from numba.typed import List

sys.path.append('.')
import bitboard

# --- FENs ---
FENS = [
    "r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8",
    "r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6",
    "rnbq1rk1/pp2bppp/4pn2/2pp4/2PP4/N4NP1/PP2PPBP/R1BQK2R w KQ - 0 7",
    "rnbqk1nr/bp3ppp/p7/3p4/P7/1N6/1PP2PPP/R1BQKBNR w KQkq - 2 8"
]

@njit(cache=True)
def get_lsb(bb):
    # Need to isolate this for Numba since lsb in bitboard is available
    return bitboard.lsb(bb)

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
    diffs[count, 2] = piece_moved if promo == 6 else promo
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
        if to == 62: # wks
            diffs[count, 0] = -1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 63; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 61; count+=1
        elif to == 58: # wqs
            diffs[count, 0] = -1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 56; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 0; diffs[count, 2] = 3; diffs[count, 3] = 59; count+=1
        elif to == 6: # bks
            diffs[count, 0] = -1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 7; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 5; count+=1
        elif to == 2: # bqs
            diffs[count, 0] = -1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 0; count+=1
            diffs[count, 0] = 1; diffs[count, 1] = 1; diffs[count, 2] = 3; diffs[count, 3] = 3; count+=1
            
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

@njit(cache=True)
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

@njit(cache=True)
def loop_classical(pieces_arr, colors_arr, state_arr, n):
    s = 0
    for i in range(n):
        s += bitboard.evaluate(pieces_arr[i], colors_arr[i], state_arr[i])
    return s

def bench_classical(pieces_arr, colors_arr, state_arr, n):
    t0 = time.time()
    s = loop_classical(pieces_arr, colors_arr, state_arr, n)
    t1 = time.time()
    return t1 - t0, s

@njit(cache=True)
def loop_nnue_full(pieces_arr, colors_arr, state_arr, n, weights, biases, weights2):
    acc = np.zeros((2, 256), dtype=np.int16)
    s = 0
    for i in range(n):
        nnue_full_refresh(pieces_arr[i], colors_arr[i], weights, biases, acc)
        turn = state_arr[i][0]
        s += nnue_eval(weights2, acc, turn)
    return s

def bench_nnue_full(pieces_arr, colors_arr, state_arr, n, weights, biases, weights2):
    t0 = time.time()
    s = loop_nnue_full(pieces_arr, colors_arr, state_arr, n, weights, biases, weights2)
    t1 = time.time()
    return t1 - t0, s

@njit(cache=True)
def loop_nnue_inc(moves_arr, turns_arr, is_make_arr, n, weights, weights2, initial_acc):
    acc = initial_acc.copy()
    diffs = np.zeros((6, 4), dtype=np.int8)
    
    s = 0
    for i in range(n):
        move = moves_arr[i]
        turn = turns_arr[i]
        is_make = is_make_arr[i]
        
        count = extract_diffs(move, turn, diffs)
        if not is_make:
            for j in range(count):
                diffs[j, 0] = -diffs[j, 0]
                
        apply_diffs(weights, acc, diffs, count)
        
        # In a real search, evaluate is called at nodes, not on every make/unmake.
        # But to be fair to classical which is evaluated per node, we measure 1 eval per make.
        if is_make:
            s += nnue_eval(weights2, acc, turn ^ 1)
            
    return s

def bench_nnue_inc(moves_arr, turns_arr, is_make_arr, n, weights, weights2, initial_acc, initial_turn):
    t0 = time.time()
    s = loop_nnue_inc(moves_arr, turns_arr, is_make_arr, n, weights, weights2, initial_acc)
    t1 = time.time()
    return t1 - t0, s

def run_perft_trace(board, depth, states, moves_trace):
    if depth == 0:
        return
    for move in board.legal_moves:
        # store state for classical eval
        p, c, s = bitboard.from_chess_board(board)
        # piece arrays etc.
        states.append((p.copy(), c.copy(), s.copy()))
        
        # move to integer
        # We need bitboard make_move format: 
        # fr (6), to (6), promo (3), piece_moved (3), captured (3), ep (1), castle (1)
        fr = move.from_square
        to = move.to_square
        promo_pt = move.promotion
        promo = bitboard.NONE
        if promo_pt == chess.KNIGHT: promo = bitboard.KNIGHT
        elif promo_pt == chess.BISHOP: promo = bitboard.BISHOP
        elif promo_pt == chess.ROOK: promo = bitboard.ROOK
        elif promo_pt == chess.QUEEN: promo = bitboard.QUEEN
        
        piece_moved = board.piece_at(fr).piece_type - 1 # pawn=0, knight=1, etc.
        captured_pc = board.piece_at(to)
        ep = 1 if board.is_en_passant(move) else 0
        castle = 1 if board.is_castling(move) else 0
        captured = captured_pc.piece_type - 1 if captured_pc else bitboard.NONE
        
        m_int = (fr) | (to << 6) | (promo << 12) | (piece_moved << 15) | (captured << 18) | (ep << 21) | (castle << 22)
        turn = 0 if board.turn == chess.WHITE else 1
        
        moves_trace.append((m_int, turn, True)) # is_make = True
        board.push(move)
        run_perft_trace(board, depth - 1, states, moves_trace)
        board.pop()
        moves_trace.append((m_int, turn, False)) # is_make = False

def run():
    print("Generating network weights...")
    np.random.seed(42)
    weights = np.random.randint(-127, 127, size=(768, 256), dtype=np.int16)
    biases = np.random.randint(-127, 127, size=(256,), dtype=np.int16)
    weights2 = np.random.randint(-127, 127, size=(512,), dtype=np.int8)
    
    # Warmup Numba JIT
    print("Warming up JIT...")
    tmp_p = np.zeros(6, dtype=np.uint64)
    tmp_c = np.zeros(2, dtype=np.uint64)
    tmp_s = np.zeros(5, dtype=np.uint64)
    tmp_acc = np.zeros((2, 256), dtype=np.int16)
    nnue_full_refresh(tmp_p, tmp_c, weights, biases, tmp_acc)
    nnue_eval(weights2, tmp_acc, 0)
    
    tmp_diffs = np.zeros((6, 4), dtype=np.int8)
    count = extract_diffs(0, 0, tmp_diffs)
    apply_diffs(weights, tmp_acc, tmp_diffs, count)
    
    # Also warmup benchmark wrappers
    # ...
    
    for fen in FENS:
        print(f"\n--- FEN: {fen} ---")
        board = chess.Board(fen)
        states = []
        moves_trace = []
        run_perft_trace(board, 3, states, moves_trace)
        
        # Prepare arrays for Numba
        n_states = len(states)
        p_arr = np.zeros((n_states, 6), dtype=np.uint64)
        c_arr = np.zeros((n_states, 2), dtype=np.uint64)
        s_arr = np.zeros((n_states, 5), dtype=np.uint64)
        for i in range(n_states):
            p_arr[i] = states[i][0]
            c_arr[i] = states[i][1]
            s_arr[i] = states[i][2]
            
        n_moves = len(moves_trace)
        m_arr = np.zeros(n_moves, dtype=np.uint32)
        turn_arr = np.zeros(n_moves, dtype=np.uint8)
        make_arr = np.zeros(n_moves, dtype=np.bool_)
        for i in range(n_moves):
            m_arr[i] = moves_trace[i][0]
            turn_arr[i] = moves_trace[i][1]
            make_arr[i] = moves_trace[i][2]
            
        print(f"Generated {n_states} states, {n_moves} incremental steps.")
        
        # Warmup bench
        bench_classical(p_arr[:1], c_arr[:1], s_arr[:1], 1)
        bench_nnue_full(p_arr[:1], c_arr[:1], s_arr[:1], 1, weights, biases, weights2)
        bench_nnue_inc(m_arr[:1], turn_arr[:1], make_arr[:1], 1, weights, weights2, tmp_acc, 0)
        
        # Run Classical
        t_class, _ = bench_classical(p_arr, c_arr, s_arr, n_states)
        evals_class = n_states / t_class
        
        # Run Full Refresh
        t_full, _ = bench_nnue_full(p_arr, c_arr, s_arr, n_states, weights, biases, weights2)
        evals_full = n_states / t_full
        
        # Run Incremental
        p_root, c_root, s_root = bitboard.from_chess_board(board)
        root_acc = np.zeros((2, 256), dtype=np.int16)
        nnue_full_refresh(p_root, c_root, weights, biases, root_acc)
        t_inc, _ = bench_nnue_inc(m_arr, turn_arr, make_arr, n_moves, weights, weights2, root_acc, 0)
        
        # n_moves is total makes + unmakes. The number of nodes is n_moves / 2.
        # So evaluating at each node is (n_moves / 2) evaluations.
        evals_inc = (n_moves / 2) / t_inc
        
        print(f"Classical Evaluate: {evals_class:,.0f} evals/sec")
        print(f"NNUE Full Refresh:  {evals_full:,.0f} evals/sec")
        print(f"NNUE Incremental:   {evals_inc:,.0f} evals/sec")
        
        k = evals_class / evals_inc
        node_rate = 1 / (0.52 + 0.48 * k)
        ply_cost = np.log(node_rate) / np.log(2.6)
        print(f"  -> implied k: {k:.2f}x cost of classical")
        print(f"  -> node rate: {node_rate:.2f}x")
        print(f"  -> ply cost:  {ply_cost:.2f} plies")

if __name__ == '__main__':
    run()
