#!/bin/bash
export PYTHONUNBUFFERED=1
FENS=(
    "r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8"
    "r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6"
    "rnbq1rk1/pp2bppp/4pn2/2pp4/2PP4/N4NP1/PP2PPBP/R1BQK2R w KQ - 0 7"
    "rnbqk1nr/bp3ppp/p7/3p4/P7/1N6/1PP2PPP/R1BQKBNR w KQkq - 2 8"
)
measure() {
    echo "--- $1 ---"
    for i in 0 1 2 3; do
        output=$(uv run python tools/measure_version.py . "${FENS[$i]}" 3000)
        nodes=$(echo "$output" | grep "Nodes:" | awk '{print $2}')
        depth=$(echo "$output" | grep "Completed Iterative Deepening Depth:" | awk -F': ' '{print $2}')
        echo "FEN $((i+1)): Depth $depth, Nodes $nodes"
    done
}

measure "All Speedups"

# Revert Speedup 3 (stand_pat)
cat << 'PYEOF' > patch.py
with open("search.py", "r") as f:
    c = f.read()
c = c.replace("            return stand_pat", "            return beta")
with open("search.py", "w") as f:
    f.write(c)
PYEOF
uv run python patch.py
measure "Without Speedup 3 (Has 1 and 2)"

# Revert Speedup 2 (promotions)
cat << 'PYEOF' > patch.py
import chess
with open("search.py", "r") as f:
    c = f.read()
old = """    if in_check:
        moves = list(ctx.board.generate_legal_moves())
        if not moves:
            return float(-(MATE_VALUE - ply))
    else:
        moves = list(ctx.board.generate_legal_captures())
        for m in ctx.board.generate_legal_moves(from_mask=chess.BB_RANK_7 | chess.BB_RANK_2, to_mask=chess.BB_RANK_8 | chess.BB_RANK_1):
            if m.promotion and not ctx.board.is_capture(m):
                moves.append(m)"""
new = """    moves = list(ctx.board.legal_moves)
    if not moves:
        if in_check:
            return float(-(MATE_VALUE - ply))
        return 0.0
        
    if not in_check:
        moves = [m for m in moves if ctx.board.is_capture(m) or m.promotion]"""
c = c.replace(old, new)
with open("search.py", "w") as f:
    f.write(c)
PYEOF
uv run python patch.py
measure "Without Speedups 2 and 3 (Has 1 only)"

git checkout search.py
rm patch.py
