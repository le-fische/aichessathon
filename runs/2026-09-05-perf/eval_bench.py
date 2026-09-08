"""Microbenchmark: piece_map() iteration versus direct bitboard iteration.

The profile shows board.piece_map() accounting for roughly half of all search
time, because it allocates a dict and a Piece object for every piece on every
call. python-chess exposes the raw bitboards, so the same sum can be computed
with no allocation at all. This measures the two against each other and checks
that they return identical scores, so the speedup can be claimed with a number
rather than an argument.
"""
import os
import sys
import time

sys.path.insert(0, os.path.expanduser("~/scratch/ab"))

import chess
from chess import scan_reversed

from evaluation import TABLE_EG, TABLE_MG, evaluate, gamephase_inc

# Flatten to plain lists indexed by [colour][piece_type] so the inner loop does
# two list index operations instead of a dict lookup plus attribute access.
PIECE_TYPES = (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING)


def evaluate_bitboards(board: chess.Board) -> float:
    """Identical result to evaluate(), without building a piece map."""
    mg_diff = 0
    eg_diff = 0
    game_phase = 0

    masks = (
        board.pawns,
        board.knights,
        board.bishops,
        board.rooks,
        board.queens,
        board.kings,
    )
    for colour in (chess.WHITE, chess.BLACK):
        own = board.occupied_co[colour]
        table_mg = TABLE_MG[colour]
        table_eg = TABLE_EG[colour]
        for piece_type, mask in zip(PIECE_TYPES, masks):
            squares = mask & own
            if not squares:
                continue
            piece_mg = table_mg[piece_type]
            piece_eg = table_eg[piece_type]
            phase_inc = gamephase_inc[piece_type]
            for square in scan_reversed(squares):
                mg_diff += piece_mg[square]
                eg_diff += piece_eg[square]
                game_phase += phase_inc

    if board.turn == chess.BLACK:
        mg_diff = -mg_diff
        eg_diff = -eg_diff

    phase = min(game_phase, 24)
    return float((mg_diff * phase + eg_diff * (24 - phase)) // 24)


FENS = [
    chess.STARTING_FEN,
    "r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8",
    "r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6",
    "rnbq1rk1/pp2bppp/4pn2/2pp4/2PP4/N4NP1/PP2PPBP/R1BQK2R w KQ - 0 7",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
    "8/8/8/3k4/8/3K4/8/6q1 b - - 10 60",
]
BOARDS = [chess.Board(fen) for fen in FENS]

# Equivalence first: a faster function that disagrees is worthless.
for board in BOARDS:
    old = evaluate(board)
    new = evaluate_bitboards(board)
    assert old == new, f"mismatch on {board.fen()}: {old} != {new}"
print(f"scores identical on all {len(BOARDS)} positions")

REPEATS = 40_000
for label, function in (("piece_map", evaluate), ("bitboards", evaluate_bitboards)):
    started = time.monotonic()
    for _ in range(REPEATS):
        for board in BOARDS:
            function(board)
    elapsed = time.monotonic() - started
    calls = REPEATS * len(BOARDS)
    print(f"{label:>10}  {elapsed:>6.2f}s for {calls} calls  {calls / elapsed:>10,.0f} eval/s")
