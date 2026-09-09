"""Do the 8 Void games still go wrong with TODAY's build?

For each void game, take the final position, then let the current engine play
BOTH sides from there for a fixed number of plies. If the engine has learned to
make progress the game reaches a real result. If it still shuffles we see the
same dead position we saw in the rated game.

Reports, per game: what result it reaches, how material moves, and how many of
the played plies were quiet (no capture, no pawn move).
"""
import os, sys, glob, collections, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("USE_NUMBA_SEARCH", "0")

import chess, chess.pgn
from search import get_move as py_get_move

VAL = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
US = "lefischer"

def material(b, c):
    return sum(VAL[p] * len(b.pieces(p, c)) for p in VAL)

def position_before_end(path, back):
    """Board `back` plies before the end, plus the real repetition counts the
    agent would have been holding at that moment."""
    g = chess.pgn.read_game(open(path))
    moves = list(g.mainline_moves())
    b = g.board()
    counts = collections.Counter()
    counts[b._transposition_key()] += 1
    for m in moves[: max(0, len(moves) - back)]:
        b.push(m)
        counts[b._transposition_key()] += 1
    us = chess.WHITE if g.headers.get("White") == US else chess.BLACK
    return b, counts, us

def playout(board, counts, plies, time_left_ms):
    b = board.copy()
    counts = collections.Counter(counts)
    quiet = 0
    for i in range(plies):
        # Stop only on a result the runner would actually record. A merely
        # CLAIMABLE threefold is not one: the rated games ran straight through
        # those, which is the whole reason we are here.
        if b.is_game_over(claim_draw=False) or b.is_fivefold_repetition() or b.is_seventyfive_moves():
            return b, b.outcome(claim_draw=True), i, quiet
        uci = py_get_move(b, time_left_ms, counts)
        mv = chess.Move.from_uci(uci)
        if mv not in b.legal_moves:
            return b, f"ILLEGAL {uci}", i, quiet
        if not (b.is_capture(mv) or b.piece_type_at(mv.from_square) == chess.PAWN):
            quiet += 1
        b.push(mv)
        counts[b._transposition_key()] += 1
    return b, None, plies, quiet

def main():
    plies = int(os.environ.get("PLIES", "60"))
    tl = int(os.environ.get("TIME_LEFT_MS", "20000"))
    print(f"replaying with {plies} plies per game, {tl}ms on the clock each move\n")
    print(f"{'game':<30}{'us':>4}{'them':>6}   {'->':<3}{'us':>4}{'them':>6}{'quiet':>7}{'plies':>7}  outcome")
    print("-" * 100)
    only = os.environ.get("GAMES", "")
    for p in sorted(glob.glob("../voided-game-logs/*.pgn")):
        name = os.path.basename(p)[13:-4]
        if only and not any(k in name for k in only.split(",")):
            continue
        b0, counts, us = position_before_end(p, int(os.environ.get("BACK", "12")))
        if b0.is_game_over(claim_draw=False):
            print(f"{name:<30}  (already over: {b0.outcome()})")
            continue
        m0u, m0t = material(b0, us), material(b0, not us)
        t = time.time()
        bf, out, n, quiet = playout(b0, counts, plies, tl)
        m1u, m1t = material(bf, us), material(bf, not us)
        desc = "shuffled, no result" if out is None else str(out)
        print(f"{name:<30}{m0u:>4}{m0t:>6}   ->{m1u:>5}{m1t:>6}{quiet:>7}{n:>7}  {desc}  [{time.time()-t:.0f}s]")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
