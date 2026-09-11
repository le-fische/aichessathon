# Round 103 conversion failure — reproduced, diagnosed, three fixes tried

## The position

    6k1/q7/P1p5/5p2/4nQp1/R2p2P1/1P6/7K w - - 0 59

White to move, 26 seconds on the clock. The game played **Rxd3**. Stockfish 18
puts Rxd3 at +0.64 and **Rb3 at +4.72** (depth 25). Not time trouble, not the
sub-3-second panic path.

## It reproduces exactly

    v12 @ 26s     Rxd3   score +219   3,470,125 nodes   1145ms
    v12 @ 260s    Rb3    score +313  24,065,816 nodes   7518ms

The engine **can** find Rb3. It needs about 7x the nodes.

## Why it needs them

    static eval after Rb3     +108 cp
    static eval after Rxd3    +343 cp

Rxd3 wins a pawn, so the evaluation prefers it by 235 cp. The search has to
out-depth its own evaluation by that margin, and 1.1 seconds does not buy it.

## Three candidate fixes, all negative

| Candidate | Result at 26s |
|---|---|
| v12 baseline | Rxd3, +219 |
| Depth-preferred TT with aging, cold table | Rxd3, +219 |
| Depth-preferred TT with aging, table saturated by replaying 103 plies | Rxd3, +197 |
| Quiet checks at the first quiescence ply | Rxd3, +222 |

The quiescence hypothesis was that Nf2+ refutes Rxd3 and is a *checking* fork,
so quiescence never sees it. Adding checks at qply 0 did not change the choice.

## What this actually says

The gap is not one bug. Closing it needs roughly 2 to 3 more plies at the same
clock, which means a large improvement in search efficiency, not a targeted fix.
That is consistent with the measured effective branching factor of 4.6 to 7.0
against 2.0 to 2.5 for a well-pruned engine. It is a v13 project, not a
night-before patch.

## The durable asset

`tools/probe/probe_position.py` and `tools/probe/probe_with_history.py` turn a
lost game into a seconds-long test. The second one replays the game first so the
transposition table is in the state the game left it, which the first one is not
a fair test of. Any future candidate should be run against these before it is
given three hours of gate time.
