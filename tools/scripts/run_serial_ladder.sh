#!/bin/bash
export PYTHONUNBUFFERED=1

echo "--- VS GREEDY (20 games) ---" > serial_ladder.log
uv run python -m harness.arena --opponent baselines/greedy --games 20 --base-ms 120000 --increment-ms 500 >> serial_ladder.log 2>&1

for d in 1 2 3 4; do
    echo "--- STOCKFISH DEPTH $d (10 games) ---" >> serial_ladder.log
    STOCKFISH_DEPTH=$d uv run python -m harness.arena --opponent baselines/stockfish --games 10 --base-ms 120000 --increment-ms 500 >> serial_ladder.log 2>&1
done
