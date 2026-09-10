"""What is 29 extra seconds on the clock actually worth, in plies?

A book that covers our first 6 moves hands the clock back. nsearch spends
budget_ms = min(0.045*t + 400, 0.25*t) per move, so the saving arrives as a
slightly larger budget on every later move. This measures completed depth at
clock c and at c + SAVED for each of the 10 real curated start FENs.
"""
import collections, glob, os, sys, time
import chess, chess.pgn
import numpy as np

assert os.environ.get("CHESSATHON_REQUIRE_NUMBA") == "1", "set CHESSATHON_REQUIRE_NUMBA=1"
sys.path.insert(0, os.path.expanduser("~/Desktop/AIChessHackathon/aichessathon"))
import nsearch

ARCHIVE = os.path.expanduser("~/Desktop/AIChessHackathon/voided-game-logs")
SAVED = 29_000
PAIRS = [(30_000, 30_000 + SAVED), (45_000, 45_000 + SAVED),
         (60_000, 60_000 + SAVED), (91_000, 91_000 + SAVED)]

fens = []
for path in sorted(glob.glob(os.path.join(ARCHIVE, "*.pgn"))):
    with open(path) as fh:
        g = chess.pgn.read_game(fh)
    fens.append((g.headers.get("Round"), g.headers.get("FEN")))


def probe(fen, clock):
    board = chess.Board(fen)
    nsearch.clear_tt()
    pieces, colors, state = nsearch.from_chess_board(board)
    pk = np.array([state[4]], dtype=np.uint64)
    pv = np.array([1], dtype=np.int32)
    t0 = time.time()
    mv, sc, nodes, depth = nsearch.numba_search(
        pieces, colors, state, clock, pk, pv, 0, t0,
        nsearch.tt_keys, nsearch.tt_depths, nsearch.tt_scores,
        nsearch.tt_flags, nsearch.tt_moves, 64)
    return depth, nodes, (time.time() - t0) * 1000


print(f"budget model: min(0.045*t + 400, 0.25*t) ms.  SAVED = {SAVED/1000:.0f} s")
for lo, hi in PAIRS:
    print(f"  clock {lo/1000:>5.0f}s -> budget {min(lo*0.045+400, lo*0.25)/1000:.2f}s | "
          f"clock {hi/1000:>5.0f}s -> budget {min(hi*0.045+400, hi*0.25)/1000:.2f}s")

print(f"\n{'rnd':>4} " + " ".join(f"{str(lo//1000)+'->'+str(hi//1000)+'s':>14}" for lo, hi in PAIRS))
deltas = {p: [] for p in PAIRS}
for rnd, fen in fens:
    cells = []
    for lo, hi in PAIRS:
        dlo, _, _ = probe(fen, lo)
        dhi, _, _ = probe(fen, hi)
        deltas[(lo, hi)].append(dhi - dlo)
        cells.append(f"{dlo:>4}->{dhi:<3}{dhi-dlo:+d}".rjust(14))
    print(f"{rnd:>4} " + " ".join(cells), flush=True)

import statistics
print()
for p in PAIRS:
    d = deltas[p]
    print(f"clock {p[0]//1000}s -> {p[1]//1000}s : mean depth gain {statistics.mean(d):+.2f} ply "
          f"(sd {statistics.stdev(d):.2f}, n={len(d)}, gained on {sum(x>0 for x in d)}/{len(d)})")
alld = [x for p in PAIRS for x in deltas[p]]
print(f"\nover all {len(alld)} paired probes: mean depth gain {statistics.mean(alld):+.3f} ply, "
      f"sd {statistics.stdev(alld):.2f}, SE {statistics.stdev(alld)/len(alld)**0.5:.3f}")
