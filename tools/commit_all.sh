#!/bin/bash
# After H2H is done, update v2 about.txt
SCORE=$(grep "score" versions/v2-morphy/results/arena_h2h_v1.log | awk -F', score ' '{print $2}')
WDL=$(grep -A 2 "\. vs versions" versions/v2-morphy/results/arena_h2h_v1.log | head -n 2 | tail -n 1 | awk -F', score' '{print $1}')
sed -i '' "s/\[PENDING_H2H\]/${SCORE} (${WDL})/g" versions/v2-morphy/about.txt

git add HANDOFF.md tests/test_fuzz.py versions/
git commit -m "chore: setup handoff, versions archive, and new benchmarks"
