set -u
R=/Users/dannybudiada/Desktop/AIChessHackathon/aichessathon
PY=/Users/dannybudiada/Desktop/AIChessHackathon/pyenv/bin/python
cd "$R"; export CHESSATHON_REQUIRE_NUMBA=1 PYTHONUNBUFFERED=1
echo "=== GATE: adaptive LMR (7b41bcc) ON vs OFF, 40 games @ 120s+0.5s === $(date)"
echo "    agent    = snapshots/lmr-on   (v12 HEAD, LMR scales with depth and move number)"
echo "    opponent = snapshots/lmr-off  (identical, reduction forced flat r=1 as v10)"
echo "    single variable: the history penalty from the same commit is in BOTH arms"
echo "    CHESSATHON_REQUIRE_NUMBA=$CHESSATHON_REQUIRE_NUMBA"
for s in lmr-on lmr-off; do
  echo "  --- $s sha256 ---"
  for f in agent.py search.py evaluation.py bitboard.py nsearch.py; do
    echo "    $(shasum -a 256 "$R/snapshots/$s/$f" | awk '{print $1"  "}')$f"
  done
done
$PY -m harness.arena --agent "$R/snapshots/lmr-on" --opponent "$R/snapshots/lmr-off" \
    --games 40 --base-ms 120000 --increment-ms 500
echo "=== GATE LMR DONE === $(date)"
