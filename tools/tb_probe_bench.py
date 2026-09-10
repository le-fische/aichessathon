"""Measure Syzygy probe latency and the engine's node rate on THIS machine.

Answers "a probe costs the equivalent of N nodes of search" for the 5-man
tablebase question. Every number here is a LOCAL-machine number; the platform
is a different CPU (AMD EPYC 9V74) and any write-up must say so.

Usage:
    CHESSATHON_REQUIRE_NUMBA=1 python tools/tb_probe_bench.py
    TB_EXTRA_DIR=~/…/tb-scratch/5man  CHESSATHON_REQUIRE_NUMBA=1 python tools/tb_probe_bench.py
"""

import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
import chess.syzygy

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WDL_DIR = os.path.join(REPO, "weights")
EXTRA_DIR = os.path.expanduser(os.environ.get("TB_EXTRA_DIR", ""))

# Positions a probe would actually fire on, one per class.
FOUR_MAN = [
    ("KRvK", "4R3/8/8/3k1K2/8/8/8/8 w - - 15 83"),
    ("KQvK", "8/8/8/3k4/8/8/4Q3/4K3 w - - 0 1"),
    ("KPvK", "8/8/8/3k4/8/4P3/8/4K3 w - - 0 1"),
    ("KBNvK", "8/8/8/4k3/8/8/8/1KBN4 w - - 0 1"),
    ("KRvKP", "8/8/8/3k4/4p3/8/8/R3K3 w - - 0 1"),
    ("KPvKP", "8/8/4p3/3k4/8/4P3/8/4K3 w - - 0 1"),
    ("KQvKR", "8/8/8/3k4/7r/8/4Q3/4K3 w - - 0 1"),
    ("KRvKN", "8/8/8/3k4/5n2/8/8/R3K3 w - - 0 1"),
]
FIVE_MAN = [
    ("KRPvKR", "8/8/8/3k4/8/4P3/7r/R3K3 w - - 0 1"),
    ("KRRvKR", "8/8/8/3k4/7r/8/8/R3K2R w - - 0 1"),
    ("KBBvKN", "8/8/8/3k4/5n2/8/8/1KBB4 w - - 0 1"),
    ("KQRvKQ", "8/8/8/3k4/6q1/8/4Q3/R3K3 w - - 0 1"),
]

BENCH_FENS = [
    ("opening", "r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8"),
    ("middlegame", "r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6"),
    ("rook-endgame", "8/5pk1/6p1/8/8/1R6/5PKP/1r6 w - - 0 40"),
    ("5-man KRPvKR", "8/8/8/3k4/8/4P3/7r/R3K3 w - - 0 1"),
    ("4-man KRvKP", "8/8/8/3k4/4p3/8/8/R3K3 w - - 0 1"),
    ("3-man KRvK", "4R3/8/8/3k1K2/8/8/8/8 w - - 15 83"),
]


def bench_probe(tb, cases, kind, reps=2000):
    print(f"\n--- {kind}: warm probe_wdl latency ({reps} reps each) ---")
    print(f"{'endgame':<10}{'median us':>12}{'mean us':>10}{'p95 us':>10}{'wdl':>6}")
    out = {}
    for name, fen in cases:
        board = chess.Board(fen)
        try:
            wdl = tb.probe_wdl(board)
        except Exception as exc:
            print(f"{name:<10}   MISSING ({type(exc).__name__}: {exc})")
            continue
        samples = []
        for _ in range(reps):
            t0 = time.perf_counter_ns()
            tb.probe_wdl(board)
            samples.append(time.perf_counter_ns() - t0)
        samples.sort()
        med = samples[len(samples) // 2] / 1000.0
        mean = statistics.mean(samples) / 1000.0
        p95 = samples[int(len(samples) * 0.95)] / 1000.0
        out[name] = med
        print(f"{name:<10}{med:>12.2f}{mean:>10.2f}{p95:>10.2f}{wdl:>6}")
    return out


def bench_first_touch(cases, dirs, label):
    """Cost of the FIRST probe of a class: open + mmap + page faults + setup.

    A 5-man probe recurses into 4-man sub-tables (python-chess probe_ab tries
    captures), so the 4-man directory has to be present for a 5-man probe to
    resolve at all. That is itself a finding: 5-man never ships alone.
    """
    print(f"\n--- first touch, fresh Tablebase object per class ({label}) ---")
    print(f"{'endgame':<10}{'open ms':>10}{'1st probe us':>15}{'2nd probe us':>15}")
    for name, fen in cases:
        board = chess.Board(fen)
        t0 = time.perf_counter_ns()
        tb = chess.syzygy.open_tablebase(dirs[0])
        for extra in dirs[1:]:
            tb.add_directory(extra)
        t1 = time.perf_counter_ns()
        try:
            tb.probe_wdl(board)
        except Exception as exc:
            print(f"{name:<10}   MISSING ({type(exc).__name__})")
            tb.close()
            continue
        t2 = time.perf_counter_ns()
        tb.probe_wdl(board)
        t3 = time.perf_counter_ns()
        print(f"{name:<10}{(t1 - t0) / 1e6:>10.2f}{(t2 - t1) / 1000:>15.1f}{(t3 - t2) / 1000:>15.1f}")
        tb.close()


def bench_dtz(directory, cases):
    print(f"\n--- probe_dtz latency, wdl={WDL_DIR} + dtz={directory} ---")
    tb = chess.syzygy.open_tablebase(WDL_DIR)
    tb.add_directory(directory)
    print(f"{'endgame':<10}{'median us':>12}{'dtz':>8}")
    for name, fen in cases:
        board = chess.Board(fen)
        try:
            dtz = tb.probe_dtz(board)
        except Exception as exc:
            print(f"{name:<10}   MISSING ({type(exc).__name__})")
            continue
        samples = []
        for _ in range(1000):
            t0 = time.perf_counter_ns()
            tb.probe_dtz(board)
            samples.append(time.perf_counter_ns() - t0)
        samples.sort()
        print(f"{name:<10}{samples[len(samples) // 2] / 1000:>12.2f}{dtz:>8}")
    tb.close()


def bench_nodes(time_left_ms=30000):
    print(f"\n--- node rate, numba search, LOCAL MACHINE (time_left_ms={time_left_ms}) ---")
    import nsearch

    print(f"{'position':<16}{'nodes':>12}{'seconds':>10}{'nodes/sec':>14}")
    rates = {}
    for name, fen in BENCH_FENS:
        board = chess.Board(fen)
        nsearch.clear_tt()
        nsearch.get_move_with_info(board.copy(), 5000, {})  # warm caches
        nsearch.clear_tt()
        t0 = time.perf_counter()
        _uci, _score, nodes = nsearch.get_move_with_info(board.copy(), time_left_ms, {})
        dt = time.perf_counter() - t0
        rates[name] = nodes / dt
        print(f"{name:<16}{nodes:>12,}{dt:>10.2f}{nodes / dt:>14,.0f}")
    return rates


def main():
    print(f"tablebase dir: {WDL_DIR}")
    tb = chess.syzygy.open_tablebase(WDL_DIR)
    if EXTRA_DIR:
        print(f"extra tablebase dir: {EXTRA_DIR}")
        tb.add_directory(EXTRA_DIR)
    four = bench_probe(tb, FOUR_MAN, "4-man shipped WDL")
    five = bench_probe(tb, FIVE_MAN, "5-man WDL")
    tb.close()

    bench_first_touch(FOUR_MAN, [WDL_DIR], "weights/ (4-man)")
    if EXTRA_DIR:
        bench_first_touch(FIVE_MAN, [WDL_DIR, EXTRA_DIR], "weights/ + extra (5-man)")

    if os.environ.get("TB_DTZ_DIR"):
        bench_dtz(os.path.expanduser(os.environ["TB_DTZ_DIR"]), FOUR_MAN)

    rates = bench_nodes()

    print("\n--- probe cost expressed in nodes of search (LOCAL) ---")
    eg_rate = rates.get("3-man KRvK") or rates.get("rook-endgame")
    print(f"reference node rate: {eg_rate:,.0f} nodes/sec (3-man KRvK, local)")
    print(f"{'endgame':<10}{'probe us':>10}{'= nodes':>12}")
    for name, med in list(four.items()) + list(five.items()):
        print(f"{name:<10}{med:>10.2f}{med * 1e-6 * eg_rate:>12,.0f}")


if __name__ == "__main__":
    main()
