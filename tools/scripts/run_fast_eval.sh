#!/bin/bash
export PYTHONUNBUFFERED=1

echo "--- GREEDY (20 games, 30s+0.3s) ---" > iteration_eval.log
uv run python -m harness.arena --opponent baselines/greedy --games 20 --base-ms 30000 --increment-ms 300 >> iteration_eval.log 2>&1

echo "--- STOCKFISH DEPTH 2 (10 games, 30s+0.3s) ---" >> iteration_eval.log
STOCKFISH_DEPTH=2 uv run python -m harness.arena --opponent baselines/stockfish --games 10 --base-ms 30000 --increment-ms 300 >> iteration_eval.log 2>&1
