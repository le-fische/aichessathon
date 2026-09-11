import sys, os, time, chess, collections
from pathlib import Path

fen = "rnbqkb1r/pp1pppp1/7p/2p5/6n1/3P4/PPPKPPPP/RNBQ1BNR w kq - 0 5"
board = chess.Board(fen)

def run_agent(agent_dir, name):
    sys.path.insert(0, str(agent_dir.resolve()))
    if 'agent' in sys.modules: del sys.modules['agent']
    if 'nsearch' in sys.modules: del sys.modules['nsearch']
    import agent
    t0 = time.time()
    # Mock position_counts (empty is fine for this)
    pos_counts = collections.Counter()
    move_str = agent.get_move(fen, 5000) # give it 5 seconds
    t1 = time.time()
    print(f"{name} played: {move_str} in {t1-t0:.2f}s")
    sys.path.pop(0)

run_agent(Path("versions/v11-kasparov"), "Baseline (v11)")
run_agent(Path("."), "Candidate (v13)")
