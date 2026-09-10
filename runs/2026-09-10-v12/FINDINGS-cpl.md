# Centipawn loss vs time spent: the clock-blunder hypothesis is inverted

Le's hypothesis: short thinking time correlates with blundering, and if bad moves cluster
at low time we need clock logic. **The data says the opposite.**

Source: the 10 v10 RATED games (rounds 80-90), 558 of our moves, each with the time spent
and clock remaining from the match log. Scored with Stockfish at depth 14.
Reproduce: `tools/cpl_analysis.py --depth 14`. Raw rows in `cpl.json`.

## Method note that changes the numbers

Evaluations are clamped to +/-1000 cp before differencing. The first run did not clamp,
and `mate_score=100000` meant a single forced mate produced a CPL near 98,000 — which put
"ALL MOVES" at a mean of 556.7 against a median of 1.0. Every mean was meaningless while
the medians were fine. Clamping is the standard ACPL convention: past a rook up, "more
winning" is not a gradient and the move that gets there is not a blunder.

## Results

                                     n   mean CPL   median   >=100cp
    ALL MOVES                      558       21.7      0.0      5.0%

    fastest quartile by time used  139       10.7      0.0      1.4%
    slowest quartile by time used  139       31.2      8.0      9.4%

    OVER budget (ratio > 1)         95       13.7      0.0      5.3%
      of those, ratio > 2           14        8.1      0.0      0.0%
    within budget (ratio <= 1)     463       23.3      1.0      5.0%

    panic path (clock < 3s)          1        0.0      0.0      0.0%
    low clock (3-10s)               35        1.0      0.0      0.0%
    mid clock (10-30s)             117       15.1      0.0      1.7%
    high clock (>30s)              405       25.4      2.0      6.4%

## What this says

**1. Slow moves blunder more, not less — 9.4% against 1.4%, a 6.7x difference.**
Time spent is a proxy for position difficulty, not a cause of accuracy. The engine spends
longer where the position is sharp, and that is where it errs. There is no clock-logic fix
implied here, because the arrow does not point the way the hypothesis assumed.

**2. The overshoots bought nothing.** The 14 moves that exceeded budget by 2-13x — including
round 90's 16.1 s on a 1,192 ms budget — had a mean CPL of 8.1 and **zero** blunders. Below
the all-move average. Thinking thirteen times longer produced no measurable accuracy.

That prices the v11 quiescence fix exactly: capping those moves at 0.85x budget costs no
accuracy, so it is a free win rather than a strength-for-safety trade. It also disposes of
the worry that the fix might weaken the engine.

**3. Low clock is where we are most accurate**, not least: 0% blunders in the 3-10 s band
against 6.4% above 30 s. Same confound — low clock arrives in simplified endgames.

**4. The panic path was reached once in 558 rated moves.** v11's panic-floor fix is correct
but close to worthless in practice. Do not spend more on it.

## Caveat, stated rather than buried

This is correlational and confounded by position type. It does **not** prove that rushing
is safe. It shows there is no evidence rushing causes blunders in our rated games, and
good evidence that thinking *beyond budget* does not help. Establishing causation would
need the same positions searched at different fixed times, which is a different experiment.
