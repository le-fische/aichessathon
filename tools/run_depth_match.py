import sys, os, time, math
from pathlib import Path
sys.path.insert(0, ".")
os.environ["USE_NUMBA_SEARCH"] = "1"
os.environ["CHESSATHON_REQUIRE_NUMBA"] = "1"
os.environ["CHESSATHON_DEPTH_LOG"] = "1"

from harness.referee import play_match
from harness.sandbox import local
from tools.ab_arena import build_book

def parse_mean_depth(stderr_text):
    depths = []
    for line in stderr_text.splitlines():
        if "info depth " in line:
            parts = line.split("info depth ")[1].split()
            try:
                depths.append(int(parts[0]))
            except: pass
    if not depths: return 0.0
    return sum(depths) / len(depths)

games = 12
base_ms = 120_000
inc_ms = 500

book = build_book(games // 2, 8, 20260905)

a_dir = Path("snapshots/match1_numba")
b_dir = Path("snapshots/match1_python")

out_file = Path("runs/2026-09-08-karpov/depth_match_results.txt")
out_file.parent.mkdir(parents=True, exist_ok=True)

with out_file.open("w") as f:
    f.write(f"Starting {games} games match for depth at {base_ms//1000}s + {inc_ms}ms\n")
    f.write("Numba: " + (a_dir / "manifest.txt").read_text() + "\n")
    f.write("Python: " + (b_dir / "manifest.txt").read_text() + "\n")

a_depth_sums = []
b_depth_sums = []

print(f"Starting {games} games match for depth")
for i in range(games):
    pair = i // 2
    a_is_white = (i % 2 == 0)
    fen = book[pair]
    
    agent_a = local(a_dir)
    agent_b = local(b_dir)
    
    white = agent_a if a_is_white else agent_b
    black = agent_b if a_is_white else agent_a
    
    outcome = play_match(white, black, base_ms, inc_ms, start_fen=fen)
        
    a_depth = parse_mean_depth(agent_a.stderr_tail)
    b_depth = parse_mean_depth(agent_b.stderr_tail)
    a_depth_sums.append(a_depth)
    b_depth_sums.append(b_depth)
    
    res_str = f"Game {i+1}: {outcome.result} | Numba depth: {a_depth:.2f}, Python depth: {b_depth:.2f}"
    print(res_str, flush=True)
    with out_file.open("a") as f:
        f.write(res_str + "\n")

final_res = f"\nMean completed depth: Numba = {sum(a_depth_sums)/len(a_depth_sums):.2f}, Python = {sum(b_depth_sums)/len(b_depth_sums):.2f}\n"
print(final_res)
with out_file.open("a") as f:
    f.write(final_res)
