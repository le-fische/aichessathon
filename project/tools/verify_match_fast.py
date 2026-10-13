import sys, os, time, math
from pathlib import Path
sys.path.insert(0, ".")
os.environ["USE_NUMBA_SEARCH"] = "1"
os.environ["CHESSATHON_REQUIRE_NUMBA"] = "1"

from harness.referee import play_match
from harness.sandbox import local
from tools.ab_arena import build_book

games = 6
base_ms = 5_000
inc_ms = 100

book = build_book(games // 2, 8, 20260905)

a_dir = Path("snapshots/v12_nnue")
b_dir = Path("snapshots/classical_baseline")

print(f"Starting {games}-game verification match at {base_ms/1000}s + {inc_ms}ms")
print(f"A (NNUE Retrained): {a_dir}")
print(f"B (Classical Baseline): {b_dir}")

wins = draws = losses = 0

for i in range(games):
    pair = i // 2
    a_is_white = (i % 2 == 0)
    fen = book[pair]
    
    agent_a = local(a_dir)
    agent_b = local(b_dir)
    
    white = agent_a if a_is_white else agent_b
    black = agent_b if a_is_white else agent_a
    
    t0 = time.time()
    outcome = play_match(white, black, base_ms, inc_ms, start_fen=fen)
    dt = time.time() - t0
    
    if outcome.result == "draw" or outcome.result == "void":
        draws += 1
    elif (outcome.result == "white") == a_is_white:
        wins += 1
    else:
        losses += 1
        
    print(f"Game {i+1}/{games}: {outcome.result} by {outcome.termination} (took {dt:.1f}s) | Running score: +{wins} ={draws} -{losses}")

score = (wins + draws / 2) / games
print(f"\nFinal Result: +{wins} ={draws} -{losses} ({score*100:.1f}%)")
