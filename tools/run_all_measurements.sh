#!/bin/bash
export PYTHONUNBUFFERED=1

echo "Starting 40 fixed node games vs v2-morphy..."
SEARCH_MAX_NODES=10000 uv run python -m harness.arena --opponent versions/v2-morphy --games 40 > runs/2026-09-03-v3/arena_fixed_nodes.log 2>&1

echo "Starting 20 time-based games vs v2-morphy..."
uv run python -m harness.arena --opponent versions/v2-morphy --games 20 --base-ms 30000 --increment-ms 300 > runs/2026-09-03-v3/arena_time_based.log 2>&1

echo "All done!"
