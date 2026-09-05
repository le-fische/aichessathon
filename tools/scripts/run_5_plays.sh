#!/bin/bash
for i in {1..5}; do
    echo "Game $i:"
    uv run python -m harness.play --white . --black versions/v2-morphy --base-ms 30000 --increment-ms 300 2>&1
done
