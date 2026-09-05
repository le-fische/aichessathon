import sys
import os
import time
import chess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bitboard

# Standard start, Kiwipete, 4 benchmarks
FENS_AND_DEPTHS = [
    (chess.STARTING_FEN, 5),
    ("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", 4),
    ("r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8", 4),
    ("r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6", 4),
    ("rnbq1rk1/pp2bppp/4pn2/2pp4/2PP4/N4NP1/PP2PPBP/R1BQK2R w KQ - 0 7", 4),
    ("rnbqk1nr/bp3ppp/p7/3p4/P7/1N6/1PP2PPP/R1BQKBNR w KQkq - 2 8", 4),
    ("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", 5),
    ("n1n5/PPPk4/8/8/8/8/4Kppp/5N1N w - - 0 1", 4),
]

def py_perft(board, depth):
    if depth == 0:
        return 1
    nodes = 0
    for move in board.legal_moves:
        board.push(move)
        nodes += py_perft(board, depth - 1)
        board.pop()
    return nodes

def test_perft(fen, depth):
    print(f"\n--- Testing {fen} Depth {depth} ---")
    board = chess.Board(fen)
    pieces, colors, state = bitboard.from_chess_board(board)
    
    t0 = time.time()
    total, valid_moves, nodes_per_move = bitboard.divide(pieces, colors, state, depth)
    t1 = time.time()
    nps = total / max(1e-6, t1-t0)
    
    print(f"My perft: {total} nodes in {t1-t0:.3f}s ({nps/1e6:.2f} Mnps)")
    
    print("Running python-chess perft...")
    py_t0 = time.time()
    py_total = 0
    py_moves = {}
    for py_move in board.legal_moves:
        board.push(py_move)
        count = py_perft(board, depth - 1)
        py_total += count
        py_moves[py_move.uci()] = count
        board.pop()
    py_t1 = time.time()
    py_nps = py_total / max(1e-6, py_t1-py_t0)
        
    print(f"python-chess perft: {py_total} nodes in {py_t1-py_t0:.3f}s ({py_nps/1e6:.2f} Mnps)")
    print(f"Speedup: {nps / max(1, py_nps):.2f}x")
    
    if total != py_total:
        print("MISMATCH!")
        return False
    else:
        print("MATCH!")
        return True

def run_all():
    print("Warming up JIT...")
    warmup_time = bitboard.warmup()
    print(f"Warmup time: {warmup_time:.3f}s")
    
    any_failed = False
    for fen, depth in FENS_AND_DEPTHS:
        if not test_perft(fen, depth):
            any_failed = True
            
    if any_failed:
        sys.exit(1)

if __name__ == "__main__":
    run_all()
