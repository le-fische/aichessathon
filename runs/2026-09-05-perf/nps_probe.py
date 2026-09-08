"""End-to-end nodes/second and depth, for the current build and a variant.

The microbenchmark measures the evaluation function alone; this measures what
the search actually gains, which is the only number worth quoting.
"""
import importlib
import os
import sys
import time

import chess

FEN = "r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8"
BUILDS = {
    "current (piece_map)": os.path.expanduser("~/scratch/ab"),
    "variant (bitboards)": os.path.expanduser("~/scratch/fasteval"),
}

for label, directory in BUILDS.items():
    sys.path.insert(0, directory)
    for module in ("search", "evaluation"):
        sys.modules.pop(module, None)
    os.environ["SEARCH_MAX_NODES"] = "3000000"
    search = importlib.import_module("search")
    assert os.path.dirname(search.__file__) == directory, search.__file__

    board = chess.Board(FEN)
    ctx = search.SearchContext(board, 10_000_000.0)
    started = time.monotonic()
    for move in list(board.legal_moves):
        ctx.board.push(move)
        search.negamax(ctx, 6, 1, -float("inf"), float("inf"))
        ctx.board.pop()
    elapsed = time.monotonic() - started
    print(f"{label:>22}  depth 7  {ctx.nodes:>9} nodes  {elapsed:>6.2f}s  {ctx.nodes / elapsed:>9,.0f} nps")
    sys.path.remove(directory)
