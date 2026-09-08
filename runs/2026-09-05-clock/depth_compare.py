"""Does v6 search shallower than v5 at the clock values real games actually see?

Games are decided by blunders in the early and middle game, so the question that
matters is not "does the policy avoid flagging" — both do — but "how deep does
each build get at the point on the clock where the game is still live".

Clock/move pairs are taken from the real match logs: round 19 ran 55 moves and
finished with 34.2 s spare; round 17 ran 75 moves and finished with 15.5 s.
"""
import importlib, os, sys, time
import chess

FENS = {
    "opening":    "r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8",
    "middlegame": "r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6",
}
# (clock remaining in ms, fullmove number)
POINTS = [(120_000, 1), (100_000, 10), (80_000, 20), (60_000, 30), (40_000, 40), (20_000, 55)]

BUILDS = {
    "v5": os.path.expanduser("~/scratch/v5"),
    "v7": os.path.expanduser("~/scratch/v7"),
}

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
        for clock, fullmove in POINTS:
            board = chess.Board(fen)
            # put the board at the right move number so moves_to_go sees it
            board.fullmove_number = fullmove
            t0 = time.monotonic()
            search.get_move(board, clock)
            elapsed = time.monotonic() - t0
            results[label][(name, clock, fullmove)] = (search.completed_depth, elapsed)
    sys.path.remove(d)

print(f"{'position':<12} {'clock':>7} {'move':>5} | {'v5 depth':>8} {'v5 s':>6} | {"v7 depth":>8} {"v7 s":>6} | delta")
worse = same = better = 0
for name in FENS:
    for clock, fullmove in POINTS:
        d5, t5 = results["v5"][(name, clock, fullmove)]
        d6, t6 = results["v7"][(name, clock, fullmove)]
        delta = d6 - d5
        if delta < 0: worse += 1
        elif delta > 0: better += 1
        else: same += 1
        mark = "" if delta == 0 else ("  v7 SHALLOWER" if delta < 0 else "  v7 deeper")
        print(f"{name:<12} {clock:>7} {fullmove:>5} | {d5:>8} {t5:>6.2f} | {d6:>8} {t6:>6.2f} | {delta:+d}{mark}")

print(f"\nv7 deeper on {better}, equal on {same}, shallower on {worse} of {better+same+worse} points")
