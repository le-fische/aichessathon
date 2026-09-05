#!/bin/bash
for i in {1..5}; do
    echo "Game $i (White: v2-morphy, Black: .)"
    uv run python -m harness.play --white versions/v2-morphy --black . --base-ms 30000 --increment-ms 300 --pgn black_game_$i.pgn > black_diag_$i.log 2>&1
done
