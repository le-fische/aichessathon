set -u
R=/Users/dannybudiada/Desktop/AIChessHackathon/aichessathon
PY=/Users/dannybudiada/Desktop/AIChessHackathon/pyenv/bin/python
cd "$R"; export CHESSATHON_REQUIRE_NUMBA=1 PYTHONUNBUFFERED=1
echo "=== GATE A: doubled/isolated pawns (5963d9c) vs v12, 40 games @ 120s+0.5s === $(date)"
echo "    agent    = snapshots/gateA-pawns   (v12 + doubled/isolated pawns)"
echo "    opponent = snapshots/gateA-control (v12 exactly)"
echo "    ship condition: 95% lower bound clears 50%"
$PY -m harness.arena --agent "$R/snapshots/gateA-pawns" --opponent "$R/snapshots/gateA-control" \
    --games 40 --base-ms 120000 --increment-ms 500
echo "=== GATE A DONE === $(date)"
