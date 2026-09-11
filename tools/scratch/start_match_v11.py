import sys, os, math, hashlib
from pathlib import Path

os.environ["CHESSATHON_REQUIRE_NUMBA"] = "1"
sys.path.insert(0, ".")

from harness.referee import play_match
from harness.sandbox import local
from tools.ab_arena import build_book

games = 30
base_ms = 120_000
inc_ms = 500

candidate_dir = Path(".")
baseline_dir = Path("versions/v11-kasparov")

print("Candidate SHA256 hashes:")
for p in sorted(candidate_dir.glob("*.py")):
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    print(f"  {sha} {p.name}")

print(f"\nStarting {games} games match at {base_ms//1000}s + {inc_ms}ms")
print(f"Candidate: {candidate_dir.resolve()}")
print(f"Baseline: {baseline_dir.resolve()}\n")

book = build_book(games // 2, 8, 20260910)

wins = draws = losses = 0
scores = []

for i in range(games):
    pair = i // 2
    a_is_white = (i % 2 == 0)
    fen = book[pair]
    
    agent_a = local(candidate_dir)
    agent_b = local(baseline_dir)
    
    white = agent_a if a_is_white else agent_b
    black = agent_b if a_is_white else agent_a
    
    outcome = play_match(white, black, base_ms, inc_ms, start_fen=fen)
    
    if outcome.result == "draw" or outcome.result == "void":
        draws += 1
        scores.append(0.5)
    elif (outcome.result == "white") == a_is_white:
        wins += 1
        scores.append(1.0)
    else:
        losses += 1
        scores.append(0.0)
        
    res_str = f"Game {i+1:2d}/{games}: {outcome.result:<5} by {outcome.termination:<10} | Candidate points: {scores[-1]}"
    print(res_str, flush=True)

score = sum(scores) / games
variance = sum((s - score)**2 for s in scores) / (games - 1) if games > 1 else 0
stderr = math.sqrt(variance / games) if games else 0.0

print(f"\nResult: +{wins} ={draws} -{losses}")
print(f"Score: {score:.1%} +/- {stderr:.1%} over {games} games")
