"""Extract and characterise the curated start FENs from our rated PGN archive."""
import glob, math, os, sys
import chess, chess.pgn

ARCHIVE = os.path.expanduser("~/Desktop/AIChessHackathon/voided-game-logs")

rows = []
for path in sorted(glob.glob(os.path.join(ARCHIVE, "*.pgn"))):
    with open(path) as fh:
        g = chess.pgn.read_game(fh)
    h = g.headers
    fen = h.get("FEN")
    b = chess.Board(fen)
    us = chess.WHITE if h.get("White") == "lefischer" else chess.BLACK
    plies = 2 * (b.fullmove_number - 1) + (0 if b.turn == chess.WHITE else 1)
    rows.append(dict(
        rnd=h.get("Round"), file=os.path.basename(path), fen=fen,
        stm="w" if b.turn else "b",
        us="W" if us else "B",
        we_move_first=(b.turn == us),
        plies=plies, halfmove=b.halfmove_clock,
        castling=b.castling_xfen().split()[2] if False else fen.split()[2],
        ep=fen.split()[3],
        pieces=len(b.piece_map()),
        term=h.get("Termination"), result=h.get("Result"),
    ))

print(f"{'rnd':>4} {'stm':>3} {'us':>2} {'1st':>4} {'ply':>4} {'hm':>3} {'cast':>5} {'ep':>3} {'pc':>3}  {'term':<13} fen")
for r in rows:
    print(f"{r['rnd']:>4} {r['stm']:>3} {r['us']:>2} {'us' if r['we_move_first'] else 'opp':>4} "
          f"{r['plies']:>4} {r['halfmove']:>3} {r['castling']:>5} {r['ep']:>3} {r['pieces']:>3}  "
          f"{r['term']:<13} {r['fen']}")

fens = [r["fen"] for r in rows]
keys = [" ".join(f.split()[:4]) for f in fens]
n = len(fens)
print(f"\ngames={n}  distinct full FEN={len(set(fens))}  distinct pos-key(4 fields)={len(set(keys))}")
print(f"we move first in {sum(r['we_move_first'] for r in rows)}/{n}; opponent moves first in {sum(not r['we_move_first'] for r in rows)}/{n}")
print(f"we are White in {sum(r['us']=='W' for r in rows)}/{n}")
print(f"black-to-move in {sum(r['stm']=='b' for r in rows)}/{n}")
print(f"plies: min {min(r['plies'] for r in rows)} max {max(r['plies'] for r in rows)} "
      f"mean {sum(r['plies'] for r in rows)/n:.1f}  odd {sum(r['plies']%2 for r in rows)}/{n}")

# Birthday bound: P(no collision in n draws from a uniform pool of size N)
def p_no_collision(n, N):
    p = 1.0
    for i in range(n):
        p *= (N - i) / N
    return p

print("\nHow big must the curated pool be to see 0 collisions in 10 draws?")
print(f"{'N':>6} {'P(no collision)':>17}")
for N in (10, 15, 20, 25, 30, 40, 50, 60, 80, 100, 150, 200, 400, 1000):
    print(f"{N:>6} {p_no_collision(n, N):>17.4f}")
lo = next(N for N in range(n, 100000) if p_no_collision(n, N) >= 0.05)
print(f"one-sided 95% lower bound on pool size N: {lo}")
lo50 = next(N for N in range(n, 100000) if p_no_collision(n, N) >= 0.50)
print(f"pool size at which a collision is 50/50: {lo50}")
