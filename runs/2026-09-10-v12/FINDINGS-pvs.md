# PVS: correct, same moves, 8.3% MORE nodes. Do not ship it.

Le rates PVS at 10-25 Elo and it is the last unrealised item on his list. It was built
twice. It is not a coding error, and it does not help this engine as it stands.

Reproduce: `tools/scratch/nsearch_pvs_instrumented.py` against `nsearch.py` via
`tools/fixed_depth_probe.py`.

## My first gate was wrong

I gated PVS on being *exact* -- same move, same score, fewer nodes -- and rejected it when
scores differed. That criterion is wrong for this engine.

`negamax` here is **fail-soft**. A null-window search that fails low returns a tighter
upper bound than a full-window search of the same node would. Both bounds are valid; the
tighter one is simply more informative about a subtree we are not going to enter. So in
fail-soft, **PVS is move-exact, not score-exact**. Requiring identical scores rejects a
correct implementation.

Measured at fixed depth 8 with the TT enabled, production conditions:

    position       base nodes    pvs nodes   change   same best move
    opening           271,262      282,761    +4.2%   yes
    middlegame        207,127      203,123    -1.9%   yes
    sharp             303,696      325,045    +7.0%   yes
    kiwipete          930,837    1,059,267   +13.8%   yes
    endgame            82,846       75,335    -9.1%   yes
    total           1,795,768    1,945,531    +8.3%

**Same move in all five.** The implementation is right.

## Why it costs nodes instead of saving them

The obvious suspect is re-searches: every null-window probe that beats alpha costs a full
window search on top. Instrumented, counting both:

    position       null-window probes   re-searches    rate
    opening                    63,778           140    0.2%
    kiwipete                  121,553            27    0.0%
    sharp                      66,116            95    0.1%
    endgame                     7,648            34    0.4%
    overall                   259,095           296    0.1%

**0.1%.** Move ordering is excellent -- TT move, then MVV-LVA with SEE, killers, history.
PVS is not paying a re-search penalty, so that is not where the nodes go.

What is left is the interaction with the transposition table. The tighter fail-low bounds
PVS produces are *worse cutoff material* for later probes than the looser bounds a
full-window search leaves behind, and `nsearch.py` stores with **always-replace and no
aging**, so the table fills with tight bounds that cut less often. The 8.3% is the search
re-deriving what a wider stored bound would have answered.

## Recommendation

**Do not ship PVS on this engine.** It is correct and it costs 8.3% of node rate for no
change in move choice.

It is likely to become a win after one of:

1. **A depth-preferred or aged TT replacement policy.** Always-replace is doing real damage
   independently of PVS -- the table hit 97-98% occupancy by move 120 in the long-game runs.
   This is probably worth more than PVS itself.
2. **Fail-hard, or clamping the fail-soft bound** before it reaches `best_score`, so the
   bounds stored resemble what plain alpha-beta would have written.

Both are v13 work. The instrumented variant and the counters are kept so nobody has to
rebuild them.

## Note on the earlier "15% more nodes with the TT disabled"

That measurement stands but was over-read. With no TT, ordering depends entirely on
killers and history, which populate differently once PVS changes which nodes are visited.
The comparison was noisier than it looked. The 8.3% above, TT on and at fixed depth, is
the number to trust.
