import os
import sys

fens = [
    "r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8",
    "r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6",
    "rnbq1rk1/pp2bppp/4pn2/2pp4/2PP4/N4NP1/PP2PPBP/R1BQK2R w KQ - 0 7",
    "rnbqk1nr/bp3ppp/p7/3p4/P7/1N6/1PP2PPP/R1BQKBNR w KQkq - 2 8"
]

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys.argv[1] == "baseline":
    sys.path.insert(0, os.path.join(repo_root, "versions/v2-morphy"))
else:
    sys.path.insert(0, repo_root)

import chess  # noqa: E402

import search  # noqa: E402

print(f"== Nodes to depth 6 for {sys.argv[1]} ==")
for i, fen in enumerate(fens):
    search.tt.clear()
    board = chess.Board(fen)
    ctx = search.SearchContext(board, 1200000.0)
    ctx.max_nodes = 5000000 # plenty
    search.negamax(ctx, 6, 1, -float('inf'), float('inf'))
    print(f"FEN {i+1}: {ctx.nodes} nodes")
