import sys; sys.path.append(".")
import sys
import os
import time
import chess

os.environ["SEARCH_MAX_NODES"] = "1000000"

# Must import one by one to avoid collision or we just reload
import nsearch
import nsearch_nnue

FENS = [
    "r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8",
    "r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6",
    "rnbq1rk1/pp2bppp/4pn2/2pp4/2PP4/N4NP1/PP2PPBP/R1BQK2R w KQ - 0 7",
    "rnbqk1nr/bp3ppp/p7/3p4/P7/1N6/1PP2PPP/R1BQKBNR w KQkq - 2 8"
]

def run():
    print("Benchmarking NPS on FENs (Classical vs NNUE 768x256 Piece-Square)...")
    for fen in FENS:
        print(f"\nFEN: {fen}")
        board = chess.Board(fen)
        pos_counts = {}
        
        # Warmup and clear TT
        nsearch.clear_tt()
        nsearch.get_move_with_info(board.copy(), 100000, pos_counts)
        nsearch_nnue.clear_tt()
        nsearch_nnue.get_move_with_info(board.copy(), 100000, pos_counts)
        
        # Measure Classical
        t0 = time.time()
        nsearch.clear_tt()
        _, _, nodes_c = nsearch.get_move_with_info(board.copy(), 100000, pos_counts)
        t1 = time.time()
        nps_c = nodes_c / (t1 - t0)
        
        # Measure NNUE
        t2 = time.time()
        nsearch_nnue.clear_tt()
        _, _, nodes_n = nsearch_nnue.get_move_with_info(board.copy(), 100000, pos_counts)
        t3 = time.time()
        nps_n = nodes_n / (t3 - t2)
        
        ratio = nps_n / nps_c
        import math
        ply_cost = math.log(ratio) / math.log(2.6)
        
        print(f"  Classical: {nps_c:,.0f} nps")
        print(f"  NNUE     : {nps_n:,.0f} nps")
        print(f"  Ratio    : {ratio:.3f}x")
        print(f"  Ply cost : {ply_cost:.2f} plies")

if __name__ == "__main__":
    run()
