set -u
R=/Users/dannybudiada/Desktop/AIChessHackathon/aichessathon
PY=/Users/dannybudiada/Desktop/AIChessHackathon/pyenv/bin/python
cd "$R"; export CHESSATHON_REQUIRE_NUMBA=1 PYTHONUNBUFFERED=1
echo "=== A/B: king safety vs same build without it, 40 games at 120s+0.5s ===  $(date)"
echo "    agent    = snapshots/v12-ks   (shelter + open files + attacker count)"
echo "    opponent = snapshots/v12-base (identical in every other respect)"
$PY -m harness.arena --agent "$R/snapshots/v12-ks" --opponent "$R/snapshots/v12-base" \
    --games 40 --base-ms 120000 --increment-ms 500
echo "=== DONE === $(date)"
