"""Does the build that actually plays ever touch the tablebase?

`weights/` holds 35 `.rtbw` files. The only `chess.syzygy` call site in the repo
is `search.py`, the pure-Python fallback. The numba path
(agent.py -> nsearch.py -> bitboard.py) has no probe. This counts probes for
real: it wraps `search.tb` in a counter and drives `agent.get_move` from
tablebase-sized positions, once with the numba search active and once with it
forced off.

Usage:
    python tools/tb_probe_counter.py            # numba active (the live build)
    USE_NUMBA_SEARCH=0 python tools/tb_probe_counter.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess

POSITIONS = [
    ("KRvK", "4R3/8/8/3k1K2/8/8/8/8 w - - 15 83"),
    ("KPvK", "8/8/8/3k4/8/4P3/8/4K3 w - - 0 1"),
    ("KRvKP", "8/8/8/3k4/4p3/8/8/R3K3 w - - 0 1"),
    ("KQvKR", "8/8/8/3k4/7r/8/4Q3/4K3 w - - 0 1"),
]


class CountingTablebase:
    def __init__(self, inner):
        self.inner = inner
        self.calls = 0

    def probe_wdl(self, board):
        self.calls += 1
        return self.inner.probe_wdl(board)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def main():
    import agent
    import search

    if search.tb is None:
        print("search.tb is None -- open_tablebase('weights') failed from cwd", os.getcwd())
        return
    counter = CountingTablebase(search.tb)
    search.tb = counter

    print(f"agent.USE_NUMBA_SEARCH = {agent.USE_NUMBA_SEARCH}")
    print(f"cwd = {os.getcwd()}\n")
    print(f"{'position':<8}{'move':>8}{'probes':>10}")
    for name, fen in POSITIONS:
        before = counter.calls
        agent.game_board = None
        mv = agent.get_move(fen, 10000)
        print(f"{name:<8}{mv:>8}{counter.calls - before:>10}")
    print(f"\ntotal probe_wdl calls: {counter.calls}")


if __name__ == "__main__":
    main()
