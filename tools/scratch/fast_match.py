import sys, os, math
from pathlib import Path

os.environ["CHESSATHON_REQUIRE_NUMBA"] = "1"
sys.path.insert(0, ".")

from harness.referee import play_match
from harness.sandbox import local

base_ms = 1_000
inc_ms = 50

candidate_dir = Path(".")
baseline_dir = Path("versions/v11-kasparov")

# Game 3 is Pair 1, Candidate is White
fen = "rnbqkb1r/pp1pppp1/7p/2p5/6n1/3P4/PPPKPPPP/RNBQ1BNR w kq - 0 5"

agent_a = local(candidate_dir)
agent_b = local(baseline_dir)

print("Starting fast Game 3...")
outcome = play_match(agent_a, agent_b, base_ms, inc_ms, start_fen=fen)
print(f"Result: {outcome.result} by {outcome.termination}")
with open("game3.pgn", "w") as f:
    f.write(outcome.pgn)
