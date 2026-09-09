"""Perft the numba move generator against python-chess.

`tests/test_perft.py` already compares `bitboard.divide` against python-chess,
but only on 8 positions and only to depth 4-5, and it is missing standard
perft positions 4, 5 and 6 as well as every known en-passant / castling /
promotion edge case.

This tool runs both generators depth by depth and prints a table. python-chess
is the ground truth. Because python-chess perft costs roughly 10 us a node, it
is skipped at any depth where our own count exceeds --py-limit, and those
cells read "skipped"; our count is still printed so a regression against a
published figure is visible.

On a mismatch the per-move divide is diffed so the offending move is named
rather than just the total.

Usage:
    CHESSATHON_REQUIRE_NUMBA=1 python tools/perft_deep.py
    CHESSATHON_REQUIRE_NUMBA=1 python tools/perft_deep.py --py-limit 5000000
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import chess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bitboard  # noqa: E402

# (tag, fen, max depth for our generator)
POSITIONS: list[tuple[str, str, int]] = [
    # The six standard perft positions.
    ("pos1-startpos", chess.STARTING_FEN, 6),
    ("pos2-kiwipete", "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", 5),
    ("pos3-endgame", "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", 6),
    ("pos4-promotions", "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1", 5),
    ("pos4-mirrored", "r2q1rk1/pP1p2pp/Q4n2/bbp1p3/Np6/1B3NBn/pPPP1PPP/R3K2R b KQ - 0 1", 5),
    ("pos5-promo-in-check", "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8", 5),
    ("pos6-steven-edwards", "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10", 5),
    # En-passant edge cases.
    ("ep-capture-checks-opponent", "8/8/8/8/k1p4R/8/3P4/3K4 w - - 0 1", 6),
    ("ep-capture-gives-check", "8/8/4k3/8/2p5/8/B2P2K1/8 w - - 0 1", 6),
    ("ep-pinned-by-bishop", "8/8/1k6/2b5/2pP4/8/5K2/8 b - d3 0 1", 6),
    ("ep-horizontal-pin", "8/8/8/8/k2Pp2Q/8/8/3K4 b - d3 0 1", 6),
    ("ep-rook-pin-on-file", "8/8/8/8/1k1Pp2R/8/8/4K3 b - d3 0 1", 6),
    # Castling edge cases.
    ("castle-short-gives-check", "5k2/8/8/8/8/8/8/4K2R w K - 0 1", 6),
    ("castle-long-gives-check", "3k4/8/8/8/8/8/8/R3K3 w Q - 0 1", 6),
    ("castle-rights-both-sides", "r3k2r/1b4bq/8/8/8/8/7B/R3K2R w KQkq - 0 1", 4),
    ("castle-prevented", "r3k2r/8/3Q4/8/8/5q2/8/R3K2R b KQkq - 0 1", 4),
    ("castle-through-attacked", "r3k2r/8/8/8/8/8/6b1/R3K2R w KQkq - 0 1", 4),
    # Promotion edge cases.
    ("promote-out-of-check", "2K2r2/4P3/8/8/8/8/8/3k4 w - - 0 1", 6),
    ("promote-to-give-check", "4k3/1P6/8/8/8/8/K7/8 w - - 0 1", 6),
    ("underpromote-to-check", "8/P1k5/K7/8/8/8/8/8 w - - 0 1", 6),
    # Stalemate / checkmate boundaries.
    ("self-stalemate", "K1k5/8/P7/8/8/8/8/8 w - - 0 1", 6),
    ("stalemate-and-checkmate-a", "8/k1P5/8/1K6/8/8/8/8 w - - 0 1", 7),
    ("stalemate-and-checkmate-b", "8/8/2k5/5q2/5n2/8/5K2/8 b - - 0 1", 5),
    ("discovered-check", "8/8/1P2K3/8/2n5/1q6/8/5k2 b - - 0 1", 5),
]


def our_perft(fen: str, depth: int) -> int:
    board = chess.Board(fen)
    pieces, colors, state = bitboard.from_chess_board(board)
    return int(bitboard.perft(pieces, colors, state, depth))


def py_perft(board: chess.Board, depth: int) -> int:
    if depth == 0:
        return 1
    if depth == 1:
        return board.legal_moves.count()
    nodes = 0
    for move in board.legal_moves:
        board.push(move)
        nodes += py_perft(board, depth - 1)
        board.pop()
    return nodes


def our_divide(fen: str, depth: int) -> dict[str, int]:
    board = chess.Board(fen)
    pieces, colors, state = bitboard.from_chess_board(board)
    _t, valid, npm = bitboard.divide(pieces, colors, state, depth)
    return {bitboard.decode_move(int(m)): int(n) for m, n in zip(valid, npm)}


def py_divide(fen: str, depth: int) -> dict[str, int]:
    board = chess.Board(fen)
    out = {}
    for move in board.legal_moves:
        board.push(move)
        out[move.uci()] = py_perft(board, depth - 1)
        board.pop()
    return out


def report_mismatch(fen: str, depth: int) -> None:
    ours = our_divide(fen, depth)
    theirs = py_divide(fen, depth)
    for uci in sorted(set(ours) | set(theirs)):
        a = ours.get(uci)
        b = theirs.get(uci)
        if a != b:
            print(f"        divide diff {uci}: ours={a} python-chess={b}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--py-limit", type=int, default=3_000_000,
                        help="skip the python-chess run at depths above this node count")
    args = parser.parse_args()

    print("warming numba...", flush=True)
    print(f"warmup {bitboard.warmup():.2f}s\n", flush=True)

    print(f"{'position':<28} {'d':>2} {'ours':>13} {'python-chess':>14} {'ours Mnps':>10}  verdict")
    print("-" * 84)

    failures = 0
    for tag, fen, maxdepth in POSITIONS:
        for depth in range(1, maxdepth + 1):
            t0 = time.perf_counter()
            ours = our_perft(fen, depth)
            dt = time.perf_counter() - t0
            mnps = ours / max(dt, 1e-9) / 1e6

            if ours <= args.py_limit:
                theirs = py_perft(chess.Board(fen), depth)
                verdict = "MATCH" if ours == theirs else "MISMATCH"
                theirs_s = f"{theirs:,}"
            else:
                theirs = None
                verdict = "skipped"
                theirs_s = "-"

            print(f"{tag:<28} {depth:>2} {ours:>13,} {theirs_s:>14} {mnps:>10.2f}  {verdict}",
                  flush=True)

            if theirs is not None and ours != theirs:
                failures += 1
                report_mismatch(fen, depth)
        print("-" * 84)

    print()
    if failures:
        print(f"FAIL: {failures} depth(s) disagree with python-chess")
    else:
        print("PASS: every depth compared against python-chess matched exactly")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
