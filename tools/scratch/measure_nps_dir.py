import sys
import time
import collections

if len(sys.argv) > 1:
    sys.path.insert(0, sys.argv[1])
else:
    sys.path.insert(0, ".")

import chess
import numpy as np

from nsearch import clear_tt, get_move_with_info, from_chess_board, numba_search, tt_keys, tt_depths, tt_scores, tt_flags, tt_moves

fens = [
    "r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8",
    "r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6",
    "rnbq1rk1/pp2bppp/4pn2/2pp4/2PP4/N4NP1/PP2PPBP/R1BQK2R w KQ - 0 7",
    "rnbqk1nr/bp3ppp/p7/3p4/P7/1N6/1PP2PPP/R1BQKBNR w KQkq - 2 8"
]

def run_to_depth6(fen):
    board = chess.Board(fen)
    clear_tt()
    
    t0 = time.monotonic()
    uci, score, nodes = get_move_with_info(board, 9999999, collections.Counter(), max_depth=6)
    t1 = time.monotonic()
    elapsed = t1 - t0
    
    return nodes, elapsed

def main():
    total_nodes = 0
    total_time = 0
    print("Measuring Nsearch Depth 6 NPS on 4 middlegame FENs...")
    for fen in fens:
        nodes, elapsed = run_to_depth6(fen)
        nps = nodes / elapsed if elapsed > 0 else 0
        print(f"FEN: {fen} | Nodes: {nodes} | Time: {elapsed:.2f}s | NPS: {nps:.0f}")
        total_nodes += nodes
        total_time += elapsed
        
    avg_nps = total_nodes / total_time if total_time > 0 else 0
    print(f"\nAverage Nsearch NPS: {avg_nps:.0f}")

if __name__ == "__main__":
    main()
