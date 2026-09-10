"""Upper bound on what an opening book could save.

For each real curated start FEN from our rated PGN archive, play a self-play game
from that FEN at the real tournament clock (120 s + 0.5 s/move, wall time charged)
and report, for OUR side only, the elapsed wall time and completed depth of each of
our first N moves. The sum of those elapsed times is the most clock a book covering
N of our moves could possibly hand back.

Runs the numba search that actually plays. CHESSATHON_REQUIRE_NUMBA=1 is mandatory.
"""
import collections, glob, os, sys, time
import chess, chess.pgn
import numpy as np

assert os.environ.get("CHESSATHON_REQUIRE_NUMBA") == "1", "set CHESSATHON_REQUIRE_NUMBA=1"

sys.path.insert(0, os.path.expanduser("~/Desktop/AIChessHackathon/aichessathon"))
import nsearch

ARCHIVE = os.path.expanduser("~/Desktop/AIChessHackathon/voided-game-logs")
START_MS = 120_000.0
INC_MS = 500.0
OURS = int(os.environ.get("OURMOVES", "6"))


def zkey(board):
    return nsearch.from_chess_board(board)[2][4]


def search_move(board, time_left_ms, counts):
    """Exactly nsearch.get_move_with_info, but also returning completed_depth."""
    pieces, colors, state = nsearch.from_chess_board(board)
    keys, vals = [], []
    for k, c in counts.items():
        if k is not None:
            keys.append(k); vals.append(c)
    pk = np.array(keys, dtype=np.uint64)
    pv = np.array(vals, dtype=np.int32)
    t0 = time.time()
    mv, score, nodes, depth = nsearch.numba_search(
        pieces, colors, state, time_left_ms, pk, pv, 0, t0,
        nsearch.tt_keys, nsearch.tt_depths, nsearch.tt_scores,
        nsearch.tt_flags, nsearch.tt_moves, 64)
    el = (time.time() - t0) * 1000.0
    if mv == 0:
        return next(iter(board.legal_moves)).uci(), 0, 0, el
    return nsearch.decode_move(mv), depth, nodes, el


games = []
for path in sorted(glob.glob(os.path.join(ARCHIVE, "*.pgn"))):
    with open(path) as fh:
        g = chess.pgn.read_game(fh)
    h = g.headers
    games.append((h.get("Round"), h.get("FEN"),
                  chess.WHITE if h.get("White") == "lefischer" else chess.BLACK))

print(f"clock {START_MS/1000:.0f}s + {INC_MS/1000:.1f}s/move, numba search, our first {OURS} moves")
print(f"{'rnd':>4} {'we':>3} " + " ".join(f"{'m'+str(i+1):>13}" for i in range(OURS))
      + f" {'our sum s':>10} {'meandepth':>10}")

allsum, alldepth, nrows = [], [], 0
detail = []
for rnd, fen, us in games:
    board = chess.Board(fen)
    nsearch.clear_tt()
    clocks = {chess.WHITE: START_MS, chess.BLACK: START_MS}
    counts = {chess.WHITE: collections.Counter(), chess.BLACK: collections.Counter()}
    ours = []
    while len(ours) < OURS and not board.is_game_over(claim_draw=True):
        side = board.turn
        counts[side][zkey(board)] += 1
        uci, depth, nodes, el = search_move(board.copy(), int(clocks[side]), counts[side])
        clocks[side] -= el
        clocks[side] += INC_MS
        if side == us:
            ours.append((el, depth, nodes))
        board.push(chess.Move.from_uci(uci))
    cells = " ".join(f"{el/1000:>6.2f}s/d{d:<4}" for el, d, _ in ours)
    s = sum(el for el, _, _ in ours) / 1000.0
    md = sum(d for _, d, _ in ours) / len(ours)
    print(f"{rnd:>4} {'W' if us else 'B':>3} {cells} {s:>9.2f}s {md:>10.2f}", flush=True)
    allsum.append(s); alldepth.append(md); nrows += 1
    detail.append((rnd, ours))

import statistics
print(f"\nour first {OURS} moves cost, mean {statistics.mean(allsum):.2f} s "
      f"(sd {statistics.stdev(allsum):.2f}, min {min(allsum):.2f}, max {max(allsum):.2f}) of a 120 s bank")
print(f"as a fraction of the 120 s base clock: {statistics.mean(allsum)/120*100:.1f}%")
print(f"mean completed depth over those moves: {statistics.mean(alldepth):.2f}")
for i in range(OURS):
    col = [d[1][i][0]/1000 for d in detail]
    cold = [d[1][i][1] for d in detail]
    print(f"  move {i+1}: mean {statistics.mean(col):.2f}s  mean depth {statistics.mean(cold):.2f}")
