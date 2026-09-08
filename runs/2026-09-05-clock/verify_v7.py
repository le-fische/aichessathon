"""Final checks on the rollback build before it ships.

It must keep what v6 fixed (K+R vs K conversion) while restoring v5's search
depth, and it must still never return an illegal move.
"""
import importlib, os, sys
import chess

D = os.path.expanduser("~/scratch/v7")
sys.path.insert(0, D)
for m in ("search", "evaluation", "agent"):
    sys.modules.pop(m, None)
os.environ.pop("SEARCH_MAX_NODES", None)
search = importlib.import_module("search")
agent = importlib.import_module("agent")
assert os.path.dirname(search.__file__) == D

MATES = {
    "K+R vs K, centre":   "8/8/8/4k3/8/8/R7/4K3 w - - 0 1",
    "K+R vs K, round 17": "6R1/8/5k2/8/8/5K2/8/8 w - - 0 1",
    "K+Q vs K, centre":   "8/8/8/4k3/8/8/Q7/4K3 w - - 0 1",
}
for name, fen in MATES.items():
    b = chess.Board(fen)
    outcome = "no mate in 70 plies"
    for _ in range(70):
        if b.is_game_over(claim_draw=True):
            outcome = b.outcome(claim_draw=True).termination.name
            break
        if b.turn == chess.WHITE:
            b.push(chess.Move.from_uci(search.get_move(b, 15_000)))
        else:
            best, bd = None, -1
            for m in b.legal_moves:
                b.push(m); sq = b.king(chess.BLACK)
                d = min(chess.square_file(sq), 7-chess.square_file(sq)) + min(chess.square_rank(sq), 7-chess.square_rank(sq))
                b.pop()
                if d > bd: bd, best = d, m
            b.push(best)
    print(f"  {name:<22} {outcome}")

# legality fuzz through agent.get_move, the platform's actual entry point
import random
rng = random.Random(7)
checked = 0
for _ in range(60):
    b = chess.Board()
    for _ in range(rng.randint(0, 60)):
        ms = list(b.legal_moves)
        if not ms: break
        b.push(rng.choice(ms))
        if b.is_game_over(claim_draw=True): break
    if b.is_game_over(claim_draw=True) or not list(b.legal_moves):
        continue
    agent.game_board = None
    uci = agent.get_move(b.fen(), 5_000)
    mv = chess.Move.from_uci(uci)
    assert mv in b.legal_moves, f"ILLEGAL {uci} in {b.fen()}"
    checked += 1
print(f"  legality: {checked} positions, zero illegal moves")
