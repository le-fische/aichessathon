#!/bin/bash
export PYTHONUNBUFFERED=1

echo "--- RUN 1: v2-morphy vs Stockfish D2 (10 games) ---" > clean_eval.log
STOCKFISH_DEPTH=2 uv run python -m harness.arena --agent versions/v2-morphy --opponent baselines/stockfish --games 10 --base-ms 30000 --increment-ms 300 >> clean_eval.log 2>&1

echo "--- RUN 2: root vs Stockfish D2 (10 games) ---" >> clean_eval.log
STOCKFISH_DEPTH=2 uv run python -m harness.arena --agent . --opponent baselines/stockfish --games 10 --base-ms 30000 --increment-ms 300 >> clean_eval.log 2>&1

echo "--- RUN 3: root vs v2-morphy (20 games) ---" >> clean_eval.log
uv run python -m harness.arena --agent . --opponent versions/v2-morphy --games 20 --base-ms 30000 --increment-ms 300 >> clean_eval.log 2>&1
