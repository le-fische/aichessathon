"""Two questions about the mate-drive term: does it stay out of the way, and does it work?

1. Equivalence everywhere else. The term is gated on exactly one side having
   nothing but a king, so on every other position the score must be unchanged,
   bit for bit. Anything else is a regression in normal play.
2. Conversion. Basic mates the old evaluation cannot find.
"""
import importlib
import os
import random
import sys

import chess

OLD = os.path.expanduser("~/scratch/ab")
NEW = os.path.expanduser("~/scratch/matedrive")


def load(directory, name):
    sys.path.insert(0, directory)
    for mod in ("search", "evaluation"):
        sys.modules.pop(mod, None)
    module = importlib.import_module(name)
    assert os.path.dirname(module.__file__) == directory, module.__file__
    sys.path.remove(directory)
    return module


# --- 1. equivalence on positions where both sides still have material --------
rng = random.Random(20260905)
positions = []
for _ in range(120):
    board = chess.Board()
    for _ in range(rng.randint(0, 120)):
        moves = list(board.legal_moves)
        if not moves:
            break
        board.push(rng.choice(moves))
        if board.is_game_over(claim_draw=True):
            break
        positions.append(board.fen())

old_eval = load(OLD, "evaluation")
old_scores = [old_eval.evaluate(chess.Board(f)) for f in positions]
new_eval = load(NEW, "evaluation")
new_scores = [new_eval.evaluate(chess.Board(f)) for f in positions]

differing = [
    (f, o, n) for f, o, n in zip(positions, old_scores, new_scores) if o != n
]
print(f"compared {len(positions)} random positions")
if differing:
    # Every difference must be a position where exactly one side is bare.
    unexpected = []
    for fen, o, n in differing:
        b = chess.Board(fen)
        w_bare = not (b.occupied_co[chess.WHITE] & ~b.kings)
        bl_bare = not (b.occupied_co[chess.BLACK] & ~b.kings)
        if w_bare == bl_bare:
            unexpected.append((fen, o, n))
    print(f"  {len(differing)} differ, all lone-king endgames: {not unexpected}")
    for fen, o, n in unexpected[:5]:
        print(f"  UNEXPECTED {o} -> {n}  {fen}")
    if unexpected:
        sys.exit(1)
else:
    print("  identical on every one")

# --- 2. does it actually convert basic mates? -------------------------------
MATES = {
    "K+R vs K, centre":  "8/8/8/4k3/8/8/R7/4K3 w - - 0 1",
    "K+R vs K, round 17": "6R1/8/5k2/8/8/5K2/8/8 w - - 0 1",
    "K+Q vs K, centre":  "8/8/8/4k3/8/8/Q7/4K3 w - - 0 1",
}
for label, directory in (("current", OLD), ("mate drive", NEW)):
    search = load(directory, "search")
    os.environ.pop("SEARCH_MAX_NODES", None)
    results = []
    for name, fen in MATES.items():
        board = chess.Board(fen)
        outcome = "no mate in 70 plies"
        for _ in range(70):
            if board.is_game_over(claim_draw=True):
                outcome = board.outcome(claim_draw=True).termination.name
                break
            if board.turn == chess.WHITE:
                board.push(chess.Move.from_uci(search.get_move(board, 15_000)))
            else:
                best, best_d = None, -1
                for m in board.legal_moves:
                    board.push(m)
                    sq = board.king(chess.BLACK)
                    d = min(chess.square_file(sq), 7 - chess.square_file(sq)) + min(
                        chess.square_rank(sq), 7 - chess.square_rank(sq))
                    board.pop()
                    if d > best_d:
                        best_d, best = d, m
                board.push(best)
        results.append(f"{name}: {outcome}")
    print(f"\n{label}:")
    for line in results:
        print(f"  {line}")
