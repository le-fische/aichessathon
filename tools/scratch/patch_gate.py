with open("tools/run_gate_match.py", "r") as f:
    text = f.read()

text = text.replace(
    'res_str = f"Game {i+1}/{games}: {outcome.result} by {outcome.termination}"',
    'res_str = f"Game {i+1}/{games}: {outcome.result} by {outcome.termination} (Clocks: W={outcome.white_clock/1000.0:.1f}s, B={outcome.black_clock/1000.0:.1f}s)"'
)
# Make sure it points to our snapshot
text = text.replace('a_dir = Path("snapshots/match3_new")', 'a_dir = Path("snapshots/nnue_candidate")')
text = text.replace('b_dir = Path("snapshots/match3_old")', 'b_dir = Path("snapshots/classical_baseline")')
text = text.replace('out_file = Path("runs/2026-09-08-karpov/match_results.txt")', 'out_file = Path("runs/2026-09-09-nnue/gate_results.txt")')

with open("tools/run_gate_match.py", "w") as f:
    f.write(text)
