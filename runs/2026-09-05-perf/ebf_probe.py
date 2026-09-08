"""Nodes required to complete each depth, and the effective branching factor.

EBF = nodes(depth) / nodes(depth-1). A well-ordered alpha-beta search with the
usual pruning sits near 2-3; anything much higher means move ordering or
pruning is leaving depth on the table, which costs far more strength than any
evaluation tweak.
"""
import os
import sys
import time

sys.path.insert(0, os.path.expanduser("~/scratch/ab"))
os.environ["SEARCH_MAX_NODES"] = "3000000"

import chess

import search

FENS = {
    "opening": "r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8",
    "middlegame": "r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6",
}

for label, fen in FENS.items():
    print(f"\n{label}: {fen}")
    print(f"{'depth':>5} {'nodes':>10} {'EBF':>6} {'seconds':>8}")
    previous = None
    for depth in range(1, 9):
        board = chess.Board(fen)
        ctx = search.SearchContext(board, 10_000_000.0)
        started = time.monotonic()
        try:
            for move in list(board.legal_moves):
                ctx.board.push(move)
                search.negamax(ctx, depth - 1, 1, -float("inf"), float("inf"))
                ctx.board.pop()
        except search.TimeUp:
            print(f"{depth:>5} {'aborted':>10}")
            break
        elapsed = time.monotonic() - started
        ebf = f"{ctx.nodes / previous:.2f}" if previous else "-"
        print(f"{depth:>5} {ctx.nodes:>10} {ebf:>6} {elapsed:>8.2f}")
        previous = ctx.nodes
        if elapsed > 25:
            break
