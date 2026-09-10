set -u
R=/Users/dannybudiada/Desktop/AIChessHackathon/aichessathon
PY=/Users/dannybudiada/Desktop/AIChessHackathon/pyenv/bin/python
cd "$R"
export CHESSATHON_REQUIRE_NUMBA=1
export PYTHONUNBUFFERED=1        # arena.py has no flush=True; without this its per-game
                                 # lines sit in an 8 KB buffer and never appear until exit
echo "=== RUN 1: v11 vs Stockfish UCI_Elo 2200, 30 games ===  $(date)"
$PY tools/vs_stockfish.py --elo 2200 --games 30
echo
echo "=== RUN 2: v11 vs frozen v10, 40 games at the real time control ===  $(date)"
$PY -m harness.arena --agent "$R/snapshots/v11" --opponent "$R/snapshots/v10" \
    --games 40 --base-ms 120000 --increment-ms 500
echo "=== DONE === $(date)"
