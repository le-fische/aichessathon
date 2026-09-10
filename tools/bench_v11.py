"""Node rate and depth for the classical numba search, on a fixed position set.

Run before and after each v11 change and compare. SEE runs on every capture in
quiescence, so a node-rate collapse is the stop condition for that change.

    CHESSATHON_REQUIRE_NUMBA=1 python tools/bench_v11.py --label before
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chess  # noqa: E402
import numpy as np  # noqa: E402

import nsearch  # noqa: E402
from bitboard import from_chess_board  # noqa: E402

EMPTY_KEYS = np.array([], dtype=np.uint64)
EMPTY_VALS = np.array([], dtype=np.int32)


def search_once(fen: str, budget_ms: int) -> tuple[int, float, int]:
    """Drive numba_search directly.

    get_move_with_info returns only (uci, score, nodes) and throws completed_depth
    away, so depth is unavailable through the normal entry point.
    """
    pieces, colors, state = from_chess_board(chess.Board(fen))
    start = time.time()
    _, _, nodes, depth = nsearch.numba_search(
        pieces, colors, state, budget_ms, EMPTY_KEYS, EMPTY_VALS, 0, start,
        nsearch.tt_keys, nsearch.tt_depths, nsearch.tt_scores,
        nsearch.tt_flags, nsearch.tt_moves, 1,
    )
    return int(nodes), time.time() - start, int(depth)

FENS = [
    ("opening", "r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8"),
    ("middlegame", "r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6"),
    ("sharp", "r2q1rk1/pp1bbppp/2np1n2/4p3/2B1P3/2NP1N2/PPPB1PPP/R2Q1RK1 w - - 4 10"),
    # heavy on captures: this is where SEE should pay for itself
    ("tactical", "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"),
    ("endgame", "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="run")
    parser.add_argument("--ms", type=int, default=3000, help="per-position budget the search is told it has")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    # warm the JIT so compilation is not counted
    nsearch.clear_tt()
    search_once(chess.STARTING_FEN, 2000)

    rows = []
    print(f"{'position':<12}{'nodes':>12}{'sec':>8}{'nodes/sec':>14}{'depth':>7}")
    for name, fen in FENS:
        nsearch.clear_tt()
        nodes, elapsed, depth = search_once(fen, args.ms)
        nps = nodes / elapsed if elapsed else 0.0
        rows.append({"position": name, "nodes": int(nodes), "sec": elapsed, "nps": nps, "depth": int(depth)})
        print(f"{name:<12}{nodes:>12,}{elapsed:>8.2f}{nps:>14,.0f}{depth:>7}")

    total_nodes = sum(r["nodes"] for r in rows)
    total_sec = sum(r["sec"] for r in rows)
    agg = total_nodes / total_sec if total_sec else 0.0
    mean_depth = sum(r["depth"] for r in rows) / len(rows)
    print(f"\naggregate {agg:,.0f} nodes/sec over {total_nodes:,} nodes, mean depth {mean_depth:.2f}")

    if args.out:
        args.out.write_text(json.dumps({"label": args.label, "aggregate_nps": agg,
                                        "mean_depth": mean_depth, "rows": rows}, indent=2))
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
