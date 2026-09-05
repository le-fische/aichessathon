import sys
import os
import importlib.util
import chess

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

def load_module_from_path(module_name: str, file_path: str):
    # Insert repo root so the loaded module can import sibling modules like evaluation
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
        
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

def run_search_to_depth(search_mod, board: chess.Board, depth_target: int):
    # Hook check_time to raise TimeUp when completed_depth == depth_target
    original_check_time = search_mod.SearchContext.check_time
    
    def hooked_check_time(self):
        original_check_time(self)
        if search_mod.completed_depth >= depth_target:
            raise search_mod.TimeUp()
            
    search_mod.SearchContext.check_time = hooked_check_time
    search_mod.tt.clear()
    
    try:
        best_uci = search_mod.get_move(board, 99999999)
    finally:
        search_mod.SearchContext.check_time = original_check_time
        
    return best_uci, search_mod.root_score

def test_equivalence(search_a_path: str, search_b_path: str):
    print(f"Comparing {search_a_path} against {search_b_path}")
    search_a = load_module_from_path("search_a", search_a_path)
    search_b = load_module_from_path("search_b", search_b_path)
    
    matches = 0
    diff_nodes = 0
    
    for fen in FENS:
        board = chess.Board(fen)
        
        ctx_a = None
        orig_init_a = search_a.SearchContext.__init__
        def hook_init_a(self, b, budget):
            nonlocal ctx_a
            orig_init_a(self, b, budget)
            ctx_a = self
        search_a.SearchContext.__init__ = hook_init_a
        
        uci_a, score_a = run_search_to_depth(search_a, board, 4)
        nodes_a = ctx_a.nodes if ctx_a else 0
        search_a.SearchContext.__init__ = orig_init_a
        
        ctx_b = None
        orig_init_b = search_b.SearchContext.__init__
        def hook_init_b(self, b, budget):
            nonlocal ctx_b
            orig_init_b(self, b, budget)
            ctx_b = self
        search_b.SearchContext.__init__ = hook_init_b
        
        uci_b, score_b = run_search_to_depth(search_b, board, 4)
        nodes_b = ctx_b.nodes if ctx_b else 0
        search_b.SearchContext.__init__ = orig_init_b
        
        print(f"FEN: {fen}")
        print(f"  A: move={uci_a} score={score_a} nodes={nodes_a}")
        print(f"  B: move={uci_b} score={score_b} nodes={nodes_b}")
        
        # root_score is by construction the exact minimax score of the move get_move returns,
        # so asserting it matches guarantees both engines found an equally strong best move.
        assert score_a == score_b, f"Root score mismatch: A={score_a}, B={score_b}"
        matches += 1
        
        if nodes_a != nodes_b:
            diff_nodes += 1
            
        print("  OK")
        
    print("\n--- Summary ---")
    print(f"Positions compared: {len(FENS)}")
    print(f"Root scores matched: {matches}/{len(FENS)}")
    print(f"Node counts differed: {diff_nodes}/{len(FENS)}")
    
    if diff_nodes == 0 and search_a_path != search_b_path:
        print("FAILURE: Zero differing node counts means perturbation never reached the search.")
        sys.exit(1)
        
    sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) == 3:
        test_equivalence(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python tests/test_search_equivalence.py <search_a.py> <search_b.py>")
        sys.exit(1)
