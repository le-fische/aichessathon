#!/bin/bash
export PYTHONUNBUFFERED=1
echo "--- GREEDY (20 games) ---" > full_eval.log
uv run python -m harness.arena --opponent baselines/greedy --games 20 --base-ms 120000 --increment-ms 500 >> full_eval.log 2>&1

for d in 1 2 3 4; do
    echo "--- STOCKFISH DEPTH $d (10 games) ---" >> full_eval.log
    STOCKFISH_DEPTH=$d uv run python -m harness.arena --opponent baselines/stockfish --games 10 --base-ms 120000 --increment-ms 500 >> full_eval.log 2>&1
done
