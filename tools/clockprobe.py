"""Depth and wall-clock spend at the clock points a real game passes through.

Two arms are compared on identical positions and identical clock values. The
gate is monotonicity: the candidate must never complete FEWER plies than the
control at any point, because the v6 regression was exactly that failure.
"""
import collections, importlib, os, sys, time
import chess

FENS = {
    "opening":    "r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8",
    "middlegame": "r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6",
    "sharp":      "r2q1rk1/pp1bbppp/2np1n2/4p3/2B1P3/2NP1N2/PPPB1PPP/R2Q1RK1 w - - 4 10",
}
POINTS = [120_000, 100_000, 80_000, 60_000, 40_000, 25_000, 15_000, 8_000]

BUILDS = {a: os.path.expanduser(f"~/ab/{a}") for a in sys.argv[1:3]}

results = {}
for label, d in BUILDS.items():
    sys.path.insert(0, d)
    for m in ("search", "evaluation"):
        sys.modules.pop(m, None)
    os.environ.pop("SEARCH_MAX_NODES", None)
    search = importlib.import_module("search")
    assert os.path.dirname(search.__file__) == d, search.__file__
    results[label] = {}
    for name, fen in FENS.items():
        for clock in POINTS:
            board = chess.Board(fen)
            search.tt.clear()
            t0 = time.monotonic()
            search.get_move(board, clock, collections.Counter())
            results[label][(name, clock)] = (search.completed_depth, time.monotonic() - t0)
    sys.path.remove(d)

a, b = list(BUILDS)
print(f"{'position':<11} {'clock':>7} | {a+' ply':>8} {a+' s':>7} | {b+' ply':>8} {b+' s':>7} | dply  dsec")
worse = same = better = 0
sa = sb = 0.0
for name in FENS:
    for clock in POINTS:
        da, ta = results[a][(name, clock)]
        db, tb = results[b][(name, clock)]
        sa += ta; sb += tb
        delta = db - da
        worse += delta < 0; better += delta > 0; same += delta == 0
        mark = "  SHALLOWER" if delta < 0 else ""
        print(f"{name:<11} {clock:>7} | {da:>8} {ta:>7.2f} | {db:>8} {tb:>7.2f} | {delta:+d}  {tb-ta:+.2f}{mark}")
print(f"\n{b}: deeper {better}, equal {same}, shallower {worse} of {better+same+worse}")
print(f"total think time  {a} {sa:.1f}s   {b} {sb:.1f}s   ({sb/sa:.2f}x)")
