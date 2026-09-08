"""Replay round 17 and find where the game was already won.

The user reports a threefold repetition drawn from a king-and-rook endgame a
rook up. If so, this is not a contempt problem: K+R vs K is a forced mate, and
an engine that cannot find it will draw whatever its draw score is.
"""
import os
import sys

sys.path.insert(0, os.path.expanduser("~/scratch/ab"))

import chess

START = "rnbq1rk1/ppp2ppp/4pn2/8/1bBP4/2N1P2P/PP3PP1/R1BQK1NR b KQ - 0 7"
VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
US = chess.WHITE  # we played White


def material(board):
    return sum(
        v * (len(board.pieces(p, US)) - len(board.pieces(p, not US))) for p, v in VALUES.items()
    )


def describe(board):
    out = []
    for colour, name in ((US, "us"), (not US, "them")):
        parts = [
            f"{len(board.pieces(p, colour))}{ch}"
            for p, ch in ((chess.QUEEN,"Q"),(chess.ROOK,"R"),(chess.BISHOP,"B"),
                          (chess.KNIGHT,"N"),(chess.PAWN,"P"))
            if len(board.pieces(p, colour))
        ]
        out.append(f"{name} K{'+' + '+'.join(parts) if parts else ' alone'}")
    return ", ".join(out)


san = open(os.path.expanduser("~/scratch/game17.san")).read().split()
board = chess.Board(START)
krk_ply = None
for i, tok in enumerate(san):
    board.push_san(tok)
    # first ply at which the position is bare K+R vs K
    if krk_ply is None and len(board.piece_map()) == 3:
        pieces = [p.piece_type for p in board.piece_map().values()]
        if sorted(pieces) == [chess.KING, chess.KING, chess.ROOK]:
            krk_ply = i + 1
            krk_fen = board.fen()

print(f"replayed {len(san)} half-moves")
print(f"final      {board.fen()}")
print(f"material   {material(board):+d}   {describe(board)}")
print(f"threefold  {board.is_repetition(3)}   halfmove clock {board.halfmove_clock}")
if krk_ply:
    print(f"\nK+R vs K reached at half-move {krk_ply} of {len(san)}")
    print(f"  {krk_fen}")
    print(f"  {len(san) - krk_ply} half-moves were played after that without mating.")

print("\nhalf-move  material  position")
board = chess.Board(START)
for i, tok in enumerate(san):
    board.push_san(tok)
    if (i + 1) % 20 == 0 or i + 1 == len(san) or (krk_ply and i + 1 == krk_ply):
        mark = "  <-- K+R vs K" if krk_ply and i + 1 == krk_ply else ""
        print(f"{i+1:>9}  {material(board):+8d}  {describe(board)}{mark}")
