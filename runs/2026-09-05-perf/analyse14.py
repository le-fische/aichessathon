"""Replay the round-14 draw and report material at every point it mattered.

The question this answers: did we repeat out of a winning position, or was the
draw already the correct result? That decides whether root-level draw avoidance
is worth building at all.
"""
import os
import sys

sys.path.insert(0, os.path.expanduser("~/scratch/ab"))

import chess

START = "r2qkb1r/1p3ppp/p1npbn2/4p1B1/4P3/N1N2P2/PPP3PP/R2QKB1R b KQkq - 3 9"
VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
WE_ARE = chess.WHITE  # we played White in this game


def material(board: chess.Board) -> int:
    """Our material minus theirs, in pawns."""
    total = 0
    for piece, value in VALUES.items():
        total += value * (
            len(board.pieces(piece, WE_ARE)) - len(board.pieces(piece, not WE_ARE))
        )
    return total


def describe(board: chess.Board) -> str:
    counts = []
    for colour, name in ((WE_ARE, "us"), (not WE_ARE, "them"),):
        parts = []
        for piece, letter in (
            (chess.QUEEN, "Q"), (chess.ROOK, "R"), (chess.BISHOP, "B"),
            (chess.KNIGHT, "N"), (chess.PAWN, "P"),
        ):
            n = len(board.pieces(piece, colour))
            if n:
                parts.append(f"{n}{letter}")
        counts.append(f"{name} {'+'.join(parts) if parts else 'bare king'}")
    return ", ".join(counts)


san = open(os.path.expanduser("~/scratch/game14.san")).read().split()
board = chess.Board(START)
history = [board.fen()]
peak = (material(board), 0)
first_repetition = None

for index, token in enumerate(san):
    try:
        board.push_san(token)
    except ValueError as error:
        print(f"stopped at token {index} ({token!r}): {error}")
        break
    balance = material(board)
    if balance > peak[0]:
        peak = (balance, index + 1)
    if first_repetition is None and board.is_repetition(2):
        first_repetition = index + 1

print(f"replayed {index + 1} of {len(san)} half-moves")
print(f"final position   {board.fen()}")
print(f"final material   {material(board):+d}   {describe(board)}")
print(f"peak material    {peak[0]:+d} at half-move {peak[1]}")
print(f"threefold now    {board.is_repetition(3)}")
print(f"first twofold    half-move {first_repetition}")
print(f"halfmove clock   {board.halfmove_clock}")

# Material trace at every 20th half-move, to see where the game turned.
board = chess.Board(START)
print("\nhalf-move  material  position")
for index, token in enumerate(san):
    board.push_san(token)
    if (index + 1) % 20 == 0 or index + 1 == len(san):
        print(f"{index + 1:>9}  {material(board):+8d}  {describe(board)}")
