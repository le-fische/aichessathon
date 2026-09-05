#!/bin/bash
set -e

echo "--- RUN A: CONTEMPT = 0.0, PENALTY = 0.0 ---"
sed -i '' 's/CONTEMPT = -40.0/CONTEMPT = 0.0/g' search.py
sed -i '' 's/NEAR_REPETITION_PENALTY = 15.0/NEAR_REPETITION_PENALTY = 0.0/g' search.py
make gate
uv run python -m harness.arena --agent . --opponent versions/v2-morphy --games 20 --base-ms 30000 --increment-ms 300

echo "--- RUN B: CONTEMPT = 0.0, PENALTY = 15.0 ---"
sed -i '' 's/NEAR_REPETITION_PENALTY = 0.0/NEAR_REPETITION_PENALTY = 15.0/g' search.py
make gate
uv run python -m harness.arena --agent . --opponent versions/v2-morphy --games 20 --base-ms 30000 --increment-ms 300

echo "--- RUN C: CONTEMPT = -40.0, PENALTY = 0.0 ---"
sed -i '' 's/CONTEMPT = 0.0/CONTEMPT = -40.0/g' search.py
sed -i '' 's/NEAR_REPETITION_PENALTY = 15.0/NEAR_REPETITION_PENALTY = 0.0/g' search.py
make gate
uv run python -m harness.arena --agent . --opponent versions/v2-morphy --games 20 --base-ms 30000 --increment-ms 300

# Restore
sed -i '' 's/NEAR_REPETITION_PENALTY = 0.0/NEAR_REPETITION_PENALTY = 15.0/g' search.py
echo "Done."
