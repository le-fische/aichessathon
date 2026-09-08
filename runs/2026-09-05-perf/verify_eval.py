"""Hard gate on the bitboard evaluation patch.

The patch is only safe if it changes nothing about which positions get searched.
Same position, same depth, same node budget: the node count must be IDENTICAL and
the chosen move must match. If the node count moves at all, the evaluation is no
longer equivalent to the one it replaced and the speed gain is meaningless.
"""
import importlib
import os
import sys
import time

import chess

FENS = {
    "opening":    "r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8",
    "middlegame": "r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6",
    "endgame":    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
}
BUILDS = {
    "before (piece_map)": os.path.expanduser("~/scratch/prepatch"),
    "after  (bitboards)": os.path.expanduser("~/scratch/ab"),
}

results: dict[str, dict[str, tuple[int, str, float]]] = {}
for label, directory in BUILDS.items():
    sys.path.insert(0, directory)
    for module in ("search", "evaluation"):
        sys.modules.pop(module, None)
    os.environ["SEARCH_MAX_NODES"] = "3000000"
    search = importlib.import_module("search")
    assert os.path.dirname(search.__file__) == directory, search.__file__
    results[label] = {}
    for name, fen in FENS.items():
        board = chess.Board(fen)
        ctx = search.SearchContext(board, 10_000_000.0)
        best, best_score = None, -float("inf")
        started = time.monotonic()
        for move in list(board.legal_moves):
            ctx.board.push(move)
            score = -search.negamax(ctx, 5, 1, -float("inf"), float("inf"))
            ctx.board.pop()
            if score > best_score:
                best_score, best = score, move
        results[label][name] = (ctx.nodes, best.uci(), time.monotonic() - started)
    sys.path.remove(directory)

ok = True
for name in FENS:
    (n0, m0, t0) = results["before (piece_map)"][name]
    (n1, m1, t1) = results["after  (bitboards)"][name]
    same = "OK " if (n0 == n1 and m0 == m1) else "FAIL"
    if same == "FAIL":
        ok = False
    print(
        f"{same} {name:<11} nodes {n0:>9} -> {n1:>9}   move {m0} -> {m1}   "
        f"{t0:>6.2f}s -> {t1:>6.2f}s   {n1 / t1 / max(n0 / t0, 1e-9):.2f}x nps"
    )
print("\nEQUIVALENT" if ok else "\nNOT EQUIVALENT - do not ship")
sys.exit(0 if ok else 1)
