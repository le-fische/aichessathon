import sys, os, time, math
from pathlib import Path
sys.path.insert(0, ".")
os.environ["USE_NUMBA_SEARCH"] = "1"
os.environ["CHESSATHON_REQUIRE_NUMBA"] = "1"

from harness.referee import play_match
from harness.sandbox import local
from tools.ab_arena import build_book

games = 60
base_ms = 120_000
inc_ms = 500

book = build_book(games // 2, 8, 20260905)

a_dir = Path("snapshots/nnue_candidate")
b_dir = Path("snapshots/classical_baseline")

out_file = Path("runs/2026-09-09-nnue/gate_results.txt")
out_file.parent.mkdir(parents=True, exist_ok=True)

with out_file.open("w") as f:
    f.write(f"Starting {games} games match at {base_ms//1000}s + {inc_ms}ms\n")
    f.write("New Numba (A): " + (a_dir / "manifest.txt").read_text() + "\n")
    f.write("Old Numba (B): " + (b_dir / "manifest.txt").read_text() + "\n")

wins = draws = losses = 0

print(f"Starting {games} games match")
for i in range(games):
    pair = i // 2
    a_is_white = (i % 2 == 0)
    fen = book[pair]
    
    agent_a = local(a_dir)
    agent_b = local(b_dir)
    
    white = agent_a if a_is_white else agent_b
    black = agent_b if a_is_white else agent_a
    
    outcome = play_match(white, black, base_ms, inc_ms, start_fen=fen)
    
    if outcome.result == "draw" or outcome.result == "void":
        draws += 1
    elif (outcome.result == "white") == a_is_white:
        wins += 1
    else:
        losses += 1
        
    res_str = f"Game {i+1}/{games}: {outcome.result} by {outcome.termination} (Clocks: W={outcome.white_clock/1000.0:.1f}s, B={outcome.black_clock/1000.0:.1f}s)"
    print(res_str, flush=True)
    with out_file.open("a") as f:
        f.write(res_str + "\n")

score = (wins + draws / 2) / games
variance = (wins * (1 - score)**2 + draws * (0.5 - score)**2 + losses * score**2) / games
stderr = math.sqrt(variance / games) if games else 0.0

final_res = f"\nMatch complete! +{wins} ={draws} -{losses}\n"
final_res += f"Score: {score:.1%} +/- {stderr:.1%} (1 sigma)\n"

print(final_res)
with out_file.open("a") as f:
    f.write(final_res)
