"""Part C: how often does our own PGN archive actually reach a tablebase-sized
position, and which material classes?

Replays every PGN in the archive and counts plies by man-count and by Syzygy
material class. The answer feeds the "which 5-man endgames are worth the
headroom" question. Note the archive is a biased sample: it is the failed games
plus one control, not a random draw from our rated results.

Usage:
    PGN_DIR=~/Desktop/AIChessHackathon/voided-game-logs python tools/tb_endgame_census.py
"""

import collections
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
import chess.pgn

PGN_DIR = os.path.expanduser(
    os.environ.get("PGN_DIR", "~/Desktop/AIChessHackathon/voided-game-logs")
)
BYTES_TSV = os.path.expanduser(
    os.environ.get("BYTES_TSV", "~/Desktop/AIChessHackathon/tb-scratch/bytes.tsv")
)

ORDER = [chess.KING, chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN]
LETTER = {
    chess.KING: "K",
    chess.QUEEN: "Q",
    chess.ROOK: "R",
    chess.BISHOP: "B",
    chess.KNIGHT: "N",
    chess.PAWN: "P",
}


def material_class(board):
    """Syzygy filename stem, stronger side first, e.g. KRPvKR."""
    sides = []
    for color in (chess.WHITE, chess.BLACK):
        s = ""
        for pt in ORDER:
            s += LETTER[pt] * len(board.pieces(pt, color))
        sides.append(s)
    a, b = sides
    if (len(a), a) < (len(b), b):
        a, b = b, a
    return f"{a}v{b}"


def load_sizes():
    w, z = {}, {}
    if not os.path.exists(BYTES_TSV):
        return w, z
    for line in open(BYTES_TSV):
        if not line.strip():
            continue
        n, name = line.rstrip("\n").split("\t")
        stem, ext = name.rsplit(".", 1)
        (w if ext == "rtbw" else z)[stem] = int(n)
    return w, z


def main():
    wsz, zsz = load_sizes()
    by_men = collections.Counter()
    games_reaching = collections.Counter()
    cls_plies = collections.Counter()
    cls_games = collections.defaultdict(set)
    total_plies = 0
    ngames = 0

    for path in sorted(glob.glob(os.path.join(PGN_DIR, "*.pgn"))):
        name = os.path.basename(path)
        with open(path) as fh:
            game = chess.pgn.read_game(fh)
        if game is None:
            continue
        ngames += 1
        board = game.board()
        seen_men = set()
        for mv in game.mainline_moves():
            board.push(mv)
            total_plies += 1
            men = chess.popcount(board.occupied)
            by_men[men] += 1
            seen_men.add(men)
            if men <= 5:
                c = material_class(board)
                cls_plies[c] += 1
                cls_games[c].add(name)
        for m in seen_men:
            games_reaching[m] += 1

    print(f"archive: {PGN_DIR}")
    print(f"games: {ngames}   plies: {total_plies}\n")

    print("plies by men on the board")
    print(f"{'men':>4}{'plies':>9}{'% of plies':>12}{'games reaching':>16}")
    for men in sorted(by_men):
        print(
            f"{men:>4}{by_men[men]:>9}{100 * by_men[men] / total_plies:>11.1f}%"
            f"{games_reaching[men]:>16}"
        )

    le5 = sum(v for k, v in by_men.items() if k <= 5)
    le4 = sum(v for k, v in by_men.items() if k <= 4)
    print(f"\nplies with <= 4 men: {le4} ({100 * le4 / total_plies:.2f}%)")
    print(f"plies with <= 5 men: {le5} ({100 * le5 / total_plies:.2f}%)")

    print("\nmaterial classes reached at <= 5 men")
    print(f"{'class':<10}{'men':>4}{'plies':>7}{'games':>7}{'wdl B':>12}{'dtz B':>12}")
    for c, n in sorted(cls_plies.items(), key=lambda kv: -kv[1]):
        men = sum(1 for ch in c if ch.isupper())
        # Syzygy orders the two sides by piece strength, not alphabetically, so
        # fall back to the mirrored stem when the alphabetical one is unknown.
        key = c if c in wsz else "v".join(reversed(c.split("v")))
        print(
            f"{c:<10}{men:>4}{n:>7}{len(cls_games[c]):>7}"
            f"{wsz.get(key, 0):>12,}{zsz.get(key, 0):>12,}"
        )


if __name__ == "__main__":
    main()
