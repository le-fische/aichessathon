#!/bin/bash
echo "Game 1 (White: ., Black: v2-morphy)"
uv run python -m harness.play --white . --black versions/v2-morphy --base-ms 30000 --increment-ms 300 > diag_1.log 2>&1
echo "Game 2 (White: v2-morphy, Black: .)"
uv run python -m harness.play --white versions/v2-morphy --black . --base-ms 30000 --increment-ms 300 > diag_2.log 2>&1
echo "Game 3 (White: ., Black: v2-morphy)"
uv run python -m harness.play --white . --black versions/v2-morphy --base-ms 30000 --increment-ms 300 > diag_3.log 2>&1
echo "Game 4 (White: v2-morphy, Black: .)"
uv run python -m harness.play --white versions/v2-morphy --black . --base-ms 30000 --increment-ms 300 > diag_4.log 2>&1
echo "Game 5 (White: ., Black: v2-morphy)"
uv run python -m harness.play --white . --black versions/v2-morphy --base-ms 30000 --increment-ms 300 > diag_5.log 2>&1
