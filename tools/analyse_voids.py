"""Forensics on the rated games that came back Void or Illegal.

Replays each PGN and reports, per game: who we were, how long it ran, whether
a threefold ever stood on the board, how much material we had at the end, and
how much of the tail was shuffling. Run:

    python tools/analyse_voids.py ../voided-game-logs
"""
import sys, os, glob, io, collections
import chess, chess.pgn

US = "lefischer"
VAL = {chess.PAWN:1, chess.KNIGHT:3, chess.BISHOP:3, chess.ROOK:5, chess.QUEEN:9}

def material(board, colour):
    return sum(VAL[p] * len(board.pieces(p, colour)) for p in VAL)

def analyse(path):
    with open(path) as fh:
        game = chess.pgn.read_game(fh)
    h = game.headers
    us_white = h.get("White") == US
    us = chess.WHITE if us_white else chess.BLACK

    board = game.board()
    counts = collections.Counter()
    counts[board._transposition_key()] += 1

    plies = 0
    first_threefold = None
    first_threefold_mover = None
    longest_quiet = 0
    quiet = 0
    shuffle_tail = 0
    moves = list(game.mainline_moves())

    for i, mv in enumerate(moves):
        cap = board.is_capture(mv) or board.piece_type_at(mv.from_square) == chess.PAWN
        mover = board.turn
        board.push(mv)
        plies += 1
        key = board._transposition_key()
        counts[key] += 1
        if counts[key] >= 3 and first_threefold is None:
            first_threefold = plies
            first_threefold_mover = "us" if mover == us else "them"
        if cap:
            quiet = 0
        else:
            quiet += 1
            longest_quiet = max(longest_quiet, quiet)

    # how many trailing plies were quiet (no capture, no pawn move)
    b2 = game.board()
    flags = []
    for mv in moves:
        flags.append(not (b2.is_capture(mv) or b2.piece_type_at(mv.from_square) == chess.PAWN))
        b2.push(mv)
    for f in reversed(flags):
        if f: shuffle_tail += 1
        else: break

    return dict(
        name=os.path.basename(path).replace("aichessathon-", "").replace(".pgn", ""),
        colour="W" if us_white else "B",
        result=h.get("Result"), term=h.get("Termination"),
        plies=plies,
        threefold=first_threefold, tf_by=first_threefold_mover,
        halfmove=board.halfmove_clock,
        mat_us=material(board, us), mat_them=material(board, not us),
        longest_quiet=longest_quiet, shuffle_tail=shuffle_tail,
        final=board.fen(),
        insufficient=board.is_insufficient_material(),
        over=board.is_game_over(claim_draw=True),
    )

def main(folder):
    rows = [analyse(p) for p in sorted(glob.glob(os.path.join(folder, "*.pgn")))]
    hdr = f"{'game':<34}{'c':<3}{'result':<8}{'term':<14}{'ply':>4}{'3fold':>7}{'by':>4}{'hmc':>5}{'us':>4}{'them':>5}{'qmax':>6}{'tail':>6}"
    print(hdr); print("-" * len(hdr))
    for r in rows:
        print(f"{r['name']:<34}{r['colour']:<3}{r['result']:<8}{r['term']:<14}{r['plies']:>4}"
              f"{str(r['threefold'] or '-'):>7}{str(r['tf_by'] or '-'):>4}{r['halfmove']:>5}"
              f"{r['mat_us']:>4}{r['mat_them']:>5}{r['longest_quiet']:>6}{r['shuffle_tail']:>6}")
    print()
    for r in rows:
        print(f"{r['name']}: final {r['final']}")
        print(f"    game_over(claim_draw=True)={r['over']}  insufficient={r['insufficient']}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../voided-game-logs")
