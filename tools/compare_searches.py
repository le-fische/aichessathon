# ruff: noqa
import collections
import sys

import chess

sys.path.insert(0, '.')
import nsearch
import search

FENS = [
    # Benchmark FENs
    "r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8",
    "r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6",
    "rnbq1rk1/pp2bppp/4pn2/2pp4/2PP4/N4NP1/PP2PPBP/R1BQK2R w KQ - 0 7",
    "rnbqk1nr/bp3ppp/p7/3p4/P7/1N6/1PP2PPP/R1BQKBNR w KQkq - 2 8",
    "4R3/8/8/3k1K2/8/8/8/8 w - - 15 83",
    
    # Random Middlegames
    "r1bq1rk1/1pp1bppp/p1n1pn2/3p4/2PP4/2N1PN2/PPQ2PPP/R1B1KB1R w KQ - 4 8",
    "r1bqk2r/pp2bppp/2n1pn2/2pp4/3P4/2N1PN2/PPP1BPPP/R1BQK2R w KQkq - 5 7",
    "r2q1rk1/pp1n1ppp/2pbpn2/3p4/2PP4/1PNQPN2/P4PPP/R1B2RK1 w - - 1 10",
    "r1bqk2r/pp3ppp/2n1pn2/2pp4/1bPP4/2N1PN2/PP3PPP/R1BQKB1R w KQkq - 3 7",
    "rnbq1rk1/pp3ppp/4pn2/2pp4/1bPP4/2N1PN2/PP1B1PPP/R2QKB1R w KQ - 4 7",
    "r1bq1rk1/pp1n1ppp/2p1pn2/3p4/2PP4/2N1PN2/PP1QBPPP/R4RK1 b - - 6 10",
    "r2q1rk1/pp1b1ppp/2n1pn2/2pp4/3P4/2N1PN2/PPPQBPPP/R4RK1 w - - 7 10",
    "r1bq1rk1/pp3ppp/2n1pn2/2pp4/2PP4/2N1PN2/PP1QBPPP/R4RK1 b - - 8 10",
    "r1bq1rk1/pp1n1ppp/2n1p3/2ppP3/3P4/2P2N2/PP1NBPPP/R2Q1RK1 b - - 0 10",
    "r2q1rk1/pp1nbppp/2n1p3/2ppP3/3P4/2PQ1N2/PP1N1PPP/R1B2RK1 w - - 1 11",
    
    # Tactical
    "r1b1k2r/pppp1ppp/2n2n2/4p3/1bB1P2q/2N2Q2/PPPP1PPP/R1B1K1NR w KQkq - 4 5",
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
    "3r1rk1/1pp2ppp/p1q2b2/4p3/4P1b1/2P2N2/PP1N1PPP/R2QR1K1 w - - 0 14",
    "r1bqk2r/ppp2ppp/2n5/3pP3/1b1P4/5N2/PP1B1PPP/R2QKB1R b KQkq - 2 9"
]

def run_nsearch(board, max_nodes=50000):
    nsearch.clear_tt()
    # Hack numba search to stop at depth 4 by overriding budget? No, we can just use OS env SEARCH_MAX_NODES
    import os
    os.environ["SEARCH_MAX_NODES"] = str(max_nodes)
    
    # We want to force depth 4. But numba search goes iterative deepening.
    # We can just run it for X nodes. But to compare root score, we need to run exactly depth 4.
    pass

def test_equiv():
    for fen in FENS:
        b = chess.Board(fen)
        print(f"--- FEN: {fen}")
        
        # Patch search.py to stop at depth 4
        orig_check_time = search.SearchContext.check_time
        def hooked_check_time(self):
            orig_check_time(self)
            if search.completed_depth >= 4:
                raise search.TimeUp()
        
        search.SearchContext.check_time = hooked_check_time
        search.tt.clear()
        
        ctx_ref = None
        orig_init = search.SearchContext.__init__
        def hook_init(self, *args, orig_init=orig_init, **kwargs):
            nonlocal ctx_ref
            orig_init(self, *args, **kwargs)
            ctx_ref = self
        search.SearchContext.__init__ = hook_init

        search.SearchContext.check_time = hooked_check_time
        search.tt.clear()
        
        try:
            m1 = search.get_move(b, 999999, collections.Counter())
        except Exception:
            m1 = search.get_move(b, 999999)
            
        search.SearchContext.check_time = orig_check_time
        search.SearchContext.__init__ = orig_init
        
        nodes1 = ctx_ref.nodes if ctx_ref else 0
        score1 = search.root_score
            
        m2, score2, nodes2 = nsearch.get_move_with_info(b, 999999, collections.Counter(), max_depth=4)
        
        print(f"  search : move={m1} score={score1} nodes={nodes1}")
        print(f"  nsearch: move={m2} score={score2} nodes={nodes2}")
        
        if score1 != score2:
            print("  MISMATCH!")

if __name__ == "__main__":
    test_equiv()
