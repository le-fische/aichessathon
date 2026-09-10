"""Offline sign and scale check for the NNUE, before it is allowed near a match.

Three gates ran roughly 155 games against an all-zero network because nothing
ever checked that the weights had loaded. This asserts the things a match cannot
tell you apart from noise: the weights are real, the evaluation is not constant,
the sign is right, and the magnitude is in centipawns rather than 64x off.
"""
import os, random, sys
os.environ["CHESSATHON_REQUIRE_NUMBA"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import chess
import nsearch_nnue as N
from nsearch import from_chess_board
import bitboard

fail = []

# 1. The weights are real, not the all-zero fallback.
nz = int(np.count_nonzero(N.weights))
print(f"weights: shape {N.weights.shape}, {nz:,} non-zero, "
      f"range [{N.weights.min()}, {N.weights.max()}]")
print(f"weights2: {int(np.count_nonzero(N.weights2)):,} non-zero")
if nz == 0:
    fail.append("weights are all zero -- the load path is still wrong")


def nnue_cp(board):
    pieces, colors, state = from_chess_board(board)
    acc = np.zeros((2, 256), dtype=np.int16)
    N.nnue_full_refresh(pieces, colors, N.weights, N.biases, acc)
    return N.nnue_eval(N.weights2, acc, state[0])


def classical_cp(board):
    pieces, colors, state = from_chess_board(board)
    return bitboard.evaluate(pieces, colors, state)


# 2. Sign check on positions where the answer is not debatable.
cases = [
    ("start, symmetric", chess.STARTING_FEN, "near zero"),
    ("white a queen up", "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "strongly +"),
    ("black a queen up", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1", "strongly -"),
    ("white a rook up", "1nbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQk - 0 1", "strongly +"),
]
print()
for name, fen, expect in cases:
    b = chess.Board(fen)
    n, c = nnue_cp(b), classical_cp(b)
    print(f"  {name:<22} nnue {n:>8.0f} cp    classical {c:>8.0f} cp    (expect {expect})")

start = nnue_cp(chess.Board())
if abs(start) > 80:
    fail.append(f"symmetric start evaluates {start:.0f} cp, expected near zero")
wq = nnue_cp(chess.Board(cases[1][1]))
bq = nnue_cp(chess.Board(cases[2][1]))
if not (wq > 150 and bq < -150):
    fail.append(f"queen-odds sign or magnitude wrong: white {wq:.0f}, black {bq:.0f}")

# 3. Not constant, and in a sane range, across a random walk.
random.seed(11)
vals, cls = [], []
b = chess.Board()
while len(vals) < 300:
    if b.is_game_over(claim_draw=False):
        b = chess.Board()
        continue
    b.push(random.choice(list(b.legal_moves)))
    vals.append(nnue_cp(b))
    cls.append(classical_cp(b))
vals, cls = np.array(vals, dtype=float), np.array(cls, dtype=float)

print()
print(f"over {len(vals)} random-walk positions:")
print(f"  nnue      mean {vals.mean():8.1f}  sd {vals.std():8.1f}  "
      f"range [{vals.min():.0f}, {vals.max():.0f}]")
print(f"  classical mean {cls.mean():8.1f}  sd {cls.std():8.1f}  "
      f"range [{cls.min():.0f}, {cls.max():.0f}]")
corr = float(np.corrcoef(vals, cls)[0, 1])
ratio = float(vals.std() / cls.std()) if cls.std() else float("nan")
print(f"  correlation with classical: {corr:+.3f}")
print(f"  sd ratio nnue/classical:    {ratio:.3f}   (1.0 means the same scale)")

if vals.std() < 5:
    fail.append(f"evaluation is nearly constant (sd {vals.std():.1f} cp)")
if corr < 0.3:
    fail.append(f"correlation with the classical evaluation is only {corr:+.3f}")

print()
if fail:
    print("FAILED:")
    for f in fail:
        print("  - " + f)
    sys.exit(1)
print("NNUE CALIBRATION OK")
