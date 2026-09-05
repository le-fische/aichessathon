#!/bin/bash
export PYTHONUNBUFFERED=1
rm -f real_ladder_d*.log
for d in 1 2 3 4; do
    echo "Starting Stockfish Depth $d"
    STOCKFISH_DEPTH=$d uv run python -m harness.arena --opponent baselines/stockfish --games 10 --base-ms 120000 --increment-ms 500 > real_ladder_d${d}.log 2>&1 &
done
wait
for d in 1 2 3 4; do
    score=$(grep "score" real_ladder_d${d}.log | awk -F', ' '{print $2}')
    wld=$(grep "score" real_ladder_d${d}.log | awk -F', ' '{print $1}')
    echo "Depth $d: $wld, $score"
done
