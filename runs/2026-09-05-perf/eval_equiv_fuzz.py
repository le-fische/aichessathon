"""Randomised equivalence check for the numba evaluation port.

Evaluation is a pure function of the position, so this can assert exact
equality rather than a tolerance. Six hand-picked positions is a weak suite for
a pure function: colour mapping, piece-type offsets and the phase clamp are all
things that pass on balanced positions and fail on lopsided ones. This walks
random legal games and compares every position reached.
"""
import os
import random
import sys

sys.path.insert(0, os.path.expanduser("~/scratch/ab"))

import chess

import bitboard
import evaluation

bitboard.warmup()

rng = random.Random(20260905)
mismatches = []
checked = 0

for game in range(120):
    board = chess.Board()
    for _ in range(rng.randint(0, 120)):
        moves = list(board.legal_moves)
        if not moves:
            break
        board.push(rng.choice(moves))
        if board.is_game_over(claim_draw=True):
            break

        expected = evaluation.evaluate(board)
        pieces, colors, state = bitboard.from_chess_board(board)
        actual = bitboard.evaluate(pieces, colors, state)
        checked += 1
        if expected != actual:
            mismatches.append((board.fen(), expected, actual))
            if len(mismatches) >= 8:
                break
    if len(mismatches) >= 8:
        break

print(f"checked {checked} random positions")
if mismatches:
    print(f"{len(mismatches)} MISMATCHES:")
    for fen, exp, act in mismatches:
        print(f"  expected {exp:>8}  got {act:>8}   {fen}")
    sys.exit(1)
print("all identical")
