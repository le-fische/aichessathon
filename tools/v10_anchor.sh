set -u
R=/Users/dannybudiada/Desktop/AIChessHackathon/aichessathon
PY=/Users/dannybudiada/Desktop/AIChessHackathon/pyenv/bin/python
cd "$R"; export CHESSATHON_REQUIRE_NUMBA=1 PYTHONUNBUFFERED=1
echo "=== v10 vs Stockfish UCI_Elo 2100, 16 games -- the rollback question ===  $(date)"
echo "    v11 scored 78.1% (+11 =3 -2) on this identical anchor"
echo "    snapshot: snapshots/v10-anchor  nsearch sha 88d79da4"
$PY tools/vs_stockfish.py --elo 2100 --games 16 --snapshot "$R/snapshots/v10-anchor"
echo "=== DONE === $(date)"
