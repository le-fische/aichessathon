"""Depth and draw-detection reached at a range of node budgets.

Answers two questions at once: how deep the search actually gets for a given
node budget, and whether the draw score (and therefore CONTEMPT) is consulted
at all at that depth.
"""
import importlib
import os
import sys
import time

PROBE = os.path.expanduser("~/scratch/probe")
sys.path.insert(0, PROBE)

import chess  # noqa: E402

FEN = "r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8"

for budget in (4_000, 20_000, 100_000, 400_000):
    os.environ["SEARCH_MAX_NODES"] = str(budget)
    for module in ("search", "evaluation"):
        if module in sys.modules:
            del sys.modules[module]
    search = importlib.import_module("search")
    search.DRAW_SCORE_CALLS[0] = 0
    board = chess.Board(FEN)
    started = time.monotonic()
    move = search.get_move(board, 120_000)
    elapsed = time.monotonic() - started
    print(
        f"nodes<={budget:>7}  depth {search.completed_depth:>2}  "
        f"{elapsed:>6.2f}s  draw-score calls {search.DRAW_SCORE_CALLS[0]:>5}  move {move}"
    )
