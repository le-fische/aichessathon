"""Where the search actually spends its time, by cumulative time.

Anything dominated by python-chess internals (generate_pseudo_legal_moves,
_attackers_mask, push/pop) is a representation cost, not an algorithm cost, and
is the part numba or a custom board can remove.
"""
import cProfile
import os
import pstats
import sys

sys.path.insert(0, os.path.expanduser("~/scratch/ab"))
os.environ["SEARCH_MAX_NODES"] = "3000000"

import chess

import search

FEN = "r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8"


def run() -> None:
    board = chess.Board(FEN)
    ctx = search.SearchContext(board, 10_000_000.0)
    for move in list(board.legal_moves):
        ctx.board.push(move)
        search.negamax(ctx, 5, 1, -float("inf"), float("inf"))
        ctx.board.pop()


profiler = cProfile.Profile()
profiler.enable()
run()
profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats("tottime").print_stats(18)
