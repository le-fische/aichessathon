"""What would a Syzygy probe actually cost INSIDE the live numba search?

The shipping path (agent.py -> nsearch.py -> bitboard.py) is @njit and carries
the position as three uint64 arrays. chess.syzygy is pure Python and wants a
chess.Board. So an in-search probe is:

    objmode boundary  +  rebuild a chess.Board from the arrays  +  probe_wdl

This measures all three, and reports the total as a multiple of one search node.

Usage:
    CHESSATHON_REQUIRE_NUMBA=1 python tools/tb_insearch_probe_cost.py
"""

import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
import chess.syzygy
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WDL_DIR = os.path.join(REPO, "weights")

CASES = [
    ("KRvK", "4R3/8/8/3k1K2/8/8/8/8 w - - 15 83"),
    ("KPvK", "8/8/8/3k4/8/4P3/8/4K3 w - - 0 1"),
    ("KRvKP", "8/8/8/3k4/4p3/8/8/R3K3 w - - 0 1"),
    ("KQvKR", "8/8/8/3k4/7r/8/4Q3/4K3 w - - 0 1"),
]

PIECE_TYPES = [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING]


def board_from_arrays(pieces, colors, state):
    """Rebuild a chess.Board from the numba representation.

    Only what probe_wdl needs: men, side to move, no castling, no ep. Syzygy
    refuses positions with castling rights anyway, and every probe fires at
    <= 5 men where castling is long gone.
    """
    board = chess.Board(None)
    white = int(colors[0])
    for idx, pt in enumerate(PIECE_TYPES):
        bb = int(pieces[idx])
        while bb:
            sq = (bb & -bb).bit_length() - 1
            bb &= bb - 1
            board._set_piece_at(sq, pt, bool((white >> sq) & 1))
    board.turn = chess.WHITE if int(state[0]) == 0 else chess.BLACK
    board.castling_rights = chess.BB_EMPTY
    board.ep_square = None
    return board


def bench(fn, reps):
    samples = []
    for _ in range(reps):
        t0 = time.perf_counter_ns()
        fn()
        samples.append(time.perf_counter_ns() - t0)
    samples.sort()
    return samples[len(samples) // 2] / 1000.0, statistics.mean(samples) / 1000.0


def main():
    from bitboard import from_chess_board

    tb = chess.syzygy.open_tablebase(WDL_DIR)
    reps = 3000

    print(f"{'endgame':<8}{'rebuild us':>12}{'probe us':>11}{'total us':>11}{'wdl':>6}{'check':>7}")
    totals = {}
    for name, fen in CASES:
        ref = chess.Board(fen)
        pieces, colors, state = from_chess_board(ref)
        rebuilt = board_from_arrays(pieces, colors, state)
        same = tb.probe_wdl(rebuilt) == tb.probe_wdl(ref)
        med_rebuild, _ = bench(lambda: board_from_arrays(pieces, colors, state), reps)
        med_probe, _ = bench(lambda: tb.probe_wdl(rebuilt), reps)

        def both():
            b = board_from_arrays(pieces, colors, state)
            tb.probe_wdl(b)

        med_total, _ = bench(both, reps)
        totals[name] = med_total
        print(
            f"{name:<8}{med_rebuild:>12.2f}{med_probe:>11.2f}{med_total:>11.2f}"
            f"{tb.probe_wdl(ref):>6}{str(same):>7}"
        )
    tb.close()

    # A single search node, measured on the same machine, same run.
    import nsearch

    board = chess.Board("4R3/8/8/3k1K2/8/8/8/8 w - - 15 83")
    nsearch.clear_tt()
    nsearch.get_move_with_info(board.copy(), 5000, {})
    nsearch.clear_tt()
    t0 = time.perf_counter()
    _uci, _sc, nodes = nsearch.get_move_with_info(board.copy(), 30000, {})
    dt = time.perf_counter() - t0
    ns_per_node = dt / nodes * 1e9
    print(f"\nsearch node cost (KRvK, local): {nodes:,} nodes in {dt:.2f} s"
          f" = {ns_per_node:.1f} ns/node = {nodes / dt:,.0f} nodes/sec")

    print("\nin-search probe cost, in nodes")
    print(f"{'endgame':<8}{'total us':>11}{'= nodes':>10}")
    for name, med in totals.items():
        print(f"{name:<8}{med:>11.2f}{med * 1000 / ns_per_node:>10,.0f}")

    print("\nif a probe fired at EVERY node at <= 5 men, effective node rate would be:")
    for name, med in totals.items():
        eff = 1e6 / (med + ns_per_node / 1000)
        print(f"  {name:<8}{eff:>12,.0f} nodes/sec  ({(nodes / dt) / eff:.0f}x slower)")


if __name__ == "__main__":
    main()
