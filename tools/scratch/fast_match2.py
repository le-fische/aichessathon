import sys, os, math
from pathlib import Path
os.environ["CHESSATHON_REQUIRE_NUMBA"] = "1"
sys.path.insert(0, ".")
from harness.referee import play_match
from harness.sandbox import local

base_ms = 1_000
inc_ms = 50

# Game 6 is Pair 2, Candidate is Black
fen = "r1bqkbnr/1ppppppp/p3n3/8/2P2PP1/1P6/P2PP2P/RNBQKBNR w KQkq - 1 5"

agent_a = local(Path("versions/v11-kasparov"))
agent_b = local(Path("."))

print("Starting fast Game 6...")
outcome = play_match(agent_a, agent_b, base_ms, inc_ms, start_fen=fen)
print(f"Result: {outcome.result} by {outcome.termination}")
with open("game6.pgn", "w") as f:
    f.write(outcome.pgn)
