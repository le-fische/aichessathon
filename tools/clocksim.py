"""Play a full self-play game with a real clock and report what is left over.

The CSV of 60 rated games says we finish with 35 s unspent on average and
41.8 s unspent in the losses. This reproduces that number for a build: it runs
an actual game, charges each search its real wall time, credits the 0.5 s
increment, and prints the clock trajectory. A policy that fixes the underspend
shows a lower "left" without ever reaching the flag.
"""
import collections, importlib, os, sys, time
import chess

START_MS = 120_000.0
INCREMENT_MS = 500.0
MAX_PLIES = int(os.environ.get("PLIES", "80"))

label = sys.argv[1]
d = os.path.expanduser(f"~/ab/{label}")
sys.path.insert(0, d)
for m in ("search", "evaluation"):
    sys.modules.pop(m, None)
search = importlib.import_module("search")
assert os.path.dirname(search.__file__) == d, search.__file__

board = chess.Board()
clocks = {chess.WHITE: START_MS, chess.BLACK: START_MS}
counts: dict[bool, collections.Counter] = {
    chess.WHITE: collections.Counter(), chess.BLACK: collections.Counter()
}
spend = {chess.WHITE: [], chess.BLACK: []}
depths = []
flagged = None

for ply in range(MAX_PLIES):
    if board.is_game_over(claim_draw=True):
        break
    side = board.turn
    counts[side][board._transposition_key()] += 1
    search.tt.clear()
    t0 = time.monotonic()
    uci = search.get_move(board.copy(), int(clocks[side]), counts[side])
    el = (time.monotonic() - t0) * 1000
    clocks[side] -= el
    if clocks[side] <= 0:
        flagged = (ply, "white" if side else "black")
        break
    clocks[side] += INCREMENT_MS
    spend[side].append(el)
    depths.append(search.completed_depth)
    board.push(chess.Move.from_uci(uci))

alls = spend[chess.WHITE] + spend[chess.BLACK]
n = len(alls)
print(f"build={label}  plies={n}  result={board.result(claim_draw=True)}  flagged={flagged}")
print(f"  clock left   white {clocks[chess.WHITE]/1000:6.1f}s   black {clocks[chess.BLACK]/1000:6.1f}s")
print(f"  spend/move   mean {sum(alls)/n/1000:.2f}s   max {max(alls)/1000:.2f}s   min {min(alls)/1000:.2f}s")
print(f"  mean depth   {sum(depths)/len(depths):.2f}   last-16 depth {sum(depths[-16:])/16:.2f}")
avail = START_MS + INCREMENT_MS * (n / 2)
print(f"  clock used   {(1 - clocks[chess.WHITE]/avail)*100:.1f}% of white's {avail/1000:.1f}s")
