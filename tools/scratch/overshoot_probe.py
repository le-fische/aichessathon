"""Reproduce and localise the long-game clock overshoot.

Calls nsearch.get_move_with_info directly at a fixed clock on the endgame positions
where tools/longgame.py measured 4-9x overshoots, and reports used-vs-budget. Point
LG_SNAP at a modified snapshot to test a candidate fix.
"""
from __future__ import annotations

import collections
import hashlib
import os
import sys
import time

SNAP = os.environ.get("LG_SNAP", os.path.join(os.path.dirname(os.path.abspath(__file__)), "longgame-snap"))
os.chdir(SNAP)
sys.path.insert(0, SNAP)

import chess  # noqa: E402
import nsearch  # noqa: E402

CASES = [
    # fen, clock_ms   -- from the ply-154 worst-overshoot position and its neighbours
    ("8/3k1P2/6K1/4p3/4P3/B7/8/8 b - - 0 86", 5182),
    ("8/3k1P2/6K1/4p3/4P3/B7/8/8 b - - 0 86", 60000),
    ("8/3k1P2/6K1/4p3/4P3/B7/8/8 b - - 0 86", 20000),
    ("8/5P2/3k2K1/4p3/4P3/B7/8/8 w - - 1 87", 5515),
    ("8/3k1P2/6K1/4p3/4P3/B7/8/8 b - - 0 86", 3500),
    # a quiet middlegame control: the abort works fine here
    ("r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6", 5182),
]


def budget(t: float) -> float:
    if t < 3000:
        return min(200.0, t * 0.1)
    return min(t * 0.045 + 400.0, t * 0.25)


print("nsearch.py sha256:", hashlib.sha256(open(os.path.join(SNAP, "nsearch.py"), "rb").read()).hexdigest())
print(f"{'clock':>7} {'budget':>8} {'hardstop':>9} {'used':>9} {'ratio':>7} {'nodes':>11} {'depth':>5}  fen")
for fen, clock in CASES:
    nsearch.clear_tt()
    board = chess.Board(fen)
    t0 = time.monotonic()
    uci, score, nodes = nsearch.get_move_with_info(board, clock, collections.Counter())
    used = (time.monotonic() - t0) * 1000
    b = budget(float(clock))
    print(f"{clock:>7} {b:>7.0f}m {b*0.85:>8.0f}m {used:>8.0f}m {used/b:>7.2f} {nodes:>11} "
          f"{'':>5}  {fen}  -> {uci}")
