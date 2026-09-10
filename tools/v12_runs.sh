set -u
R=/Users/dannybudiada/Desktop/AIChessHackathon/aichessathon
PY=/Users/dannybudiada/Desktop/AIChessHackathon/pyenv/bin/python
cd "$R"; export CHESSATHON_REQUIRE_NUMBA=1 PYTHONUNBUFFERED=1
echo "=== A: 600-ply endurance with RSS, v12 (Syzygy build) ===  $(date)"
LG_SNAP=$R/snapshots/v12 LG_OUT=$R/runs/2026-09-10-v12 LG_TAG=-v12-endurance LG_PLIES=600 \
  $PY tools/longgame.py
echo
for ELO in 1700 1900 2100; do
  echo "=== B: calibration anchor UCI_Elo $ELO, 16 games ===  $(date)"
  $PY tools/vs_stockfish.py --elo $ELO --games 16
  echo
done
echo "=== DONE === $(date)"
