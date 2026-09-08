"""Depth by MOVE NUMBER over a long game -- the metric clockprobe cannot see.

clockprobe compares depth at a given clock value, which is monotone by
construction for an additive policy. But a policy that spends more ARRIVES at
low clock sooner, so depth at a given move number is a different question and
it is the one that decides games. This charges each policy its real wall time
move after move from a fixed position and reports depth against move number,
plus the floor the clock converges to.
"""
import collections, importlib, os, sys, time
import chess

FEN = "r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6"
MOVES = int(os.environ.get("MOVES", "70"))
INC = 500.0
out = {}
for label in sys.argv[1:]:
    d = os.path.expanduser(f"~/ab/{label}")
    sys.path.insert(0, d)
    for m in ("search", "evaluation"):
        sys.modules.pop(m, None)
    search = importlib.import_module("search")
    assert os.path.dirname(search.__file__) == d, search.__file__
    clock, depths, flagged = 120_000.0, [], None
    for i in range(1, MOVES + 1):
        search.tt.clear()
        t0 = time.monotonic()
        search.get_move(chess.Board(FEN), int(clock), collections.Counter())
        clock -= (time.monotonic() - t0) * 1000
        if clock <= 0:
            flagged = i
            break
        clock += INC
        depths.append(search.completed_depth)
    out[label] = (depths, clock, flagged)
    sys.path.remove(d)

print(f"{'build':<8} {'d1-20':>6} {'d21-45':>7} {'d46-70':>7} {'floor':>8} {'flag':>6}")
for label, (dp, clock, fl) in out.items():
    a = sum(dp[0:20]) / max(1, len(dp[0:20]))
    b = sum(dp[20:45]) / max(1, len(dp[20:45]))
    c = sum(dp[45:70]) / max(1, len(dp[45:70]))
    print(f"{label:<8} {a:>6.2f} {b:>7.2f} {c:>7.2f} {clock/1000:>7.1f}s {str(fl):>6}")
