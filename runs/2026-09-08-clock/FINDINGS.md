# Time policy: we were leaving a third of the clock unspent

## What the rated games say

All 60 rated games, from the dashboard's per-game CSV (clock statistics, not
PGNs). Available clock is 120 s + 0.5 s per move.

|         | used  | left   | avg/move | moves |
|---------|-------|--------|----------|-------|
| all     | 74.6% | 35.0 s | 2.41 s   | --    |
| wins    | 74.7% | 35.3 s | 2.45 s   | 46    |
| draws   | 78.4% | 29.8 s | 2.31 s   | 65    |
| losses  | 69.1% | 41.8 s | 2.56 s   | 43    |

Losses are the *least*-spent class. We were being checkmated on move 43 while
holding 42 seconds.

## Why

`budget_ms = 0.045 * time_left + 400` is a fixed ~1/22 of the time REMAINING.
That decays geometrically while the game does not, so the budget shrinks fastest
in the endgame -- the phase where the CSV says we draw and lose. It is not a
mistuned constant, it is the wrong shape: a policy proportional to the remainder
can never spend the remainder.

## The change

    budget_ms = min(time_left_ms * 0.065 + 400.0, time_left_ms * 0.25)
    budget_ms = min(budget_ms + INCREMENT_MS * 0.8, time_left_ms * 0.25)

Coefficient 0.045 -> 0.065, plus 400 ms of the guaranteed 500 ms increment.
The increment term is self-financing: it is replaced every move, so it cannot
bankrupt the clock. Both terms are strictly additive to the reverted v5 policy,
so depth at any clock point can only rise.

## Gate

v6 regressed on exactly this file, and it regressed because the policy was
scored on *clock left* and never on *depth*. So depth is the gate.

`tools/clockprobe.py` -- completed depth and wall time for both arms at the same
3 positions x 8 clock values:

    cclock: deeper 12, equal 12, shallower 0 of 24
    total think time  cur 55.6 s   cclock 76.2 s  (1.37x)

Zero points shallower. Half of all points gain a full ply.

`tools/clocksim.py` -- an 80-ply self-play game charging each search its real
wall time and crediting the increment:

    cur     74.5% used, 35.7 s left, mean depth 6.05, no flag
    cclock  87.8% used, 17.1 s left, mean depth 6.26, no flag

The control arm reproduces the rated games (74.5% / 35.7 s against the real
74.6% / 35.0 s), which is what makes the candidate number trustworthy.

## Rejected on the way

`cand3` also raised the iterative-deepening cutoff from budget/2 to budget*0.62.
It spent more (91.6% used, 11.8 s left) and searched SHALLOWER (mean depth 6.20
vs 6.38, last-16-ply depth 6.00 vs 6.62): the higher cutoff starts iterations it
cannot finish, so the extra time goes into aborted searches. Keep budget/2.

## Not a gate

A hand-written 8-position tactical suite was tried and discarded. Both arms
scored 2/8 with identical misses, and at least one expected move in it was
simply wrong (Qxf7 is not mate in that position). The suite measured the author,
not the engine. Do not resurrect it without ground truth from an outside source.

---

# Correction: clockprobe was the wrong gate, and 0.065 was too aggressive

The monotonicity result above is real and it is not sufficient. clockprobe
compares completed depth at a given CLOCK VALUE. For a policy that only adds to
the budget, that comparison is monotone by construction -- it cannot come back
negative, so it cannot fail, so it is not a gate. What it missed is that a
policy which spends more ARRIVES at a low clock sooner. Depth by MOVE NUMBER is
a different question and it is the one that decides games.

This was found by running the packaged zip through a 120-ply game before
uploading: both sides were down to 3.0 s by move 60, on a policy whose 80-ply
simulation had reported a comfortable 17 s left. The self-play game in clocksim
ends when the game ends (84 plies), so it never exercised the tail. Our
threefold draws average 65 moves and the ply cap is 300.

`tools/clocktraj.py` charges each policy its real wall time move after move from
a fixed position, so the trajectory is observed for as long as we want
regardless of how a game would have finished. Mean completed depth by phase over
70 moves:

| build            | d1-20 | d21-45 | d46-70 | floor  | flag |
|------------------|-------|--------|--------|--------|------|
| 0.045 (shipped)  | 6.55  | 6.00   | 5.24   | 20.6 s | none |
| 0.050 + inc      | 6.80  | 6.00   | 5.20   | 10.4 s | none |
| 0.055 + inc      | 6.80  | 6.00   | 5.04   |  8.8 s | none |
| 0.065 + inc      | 6.90  | 5.88   | 5.00   |  4.7 s | none |

0.065 buys 0.35 ply in the opening by giving back 0.12 ply in the middlegame and
0.24 in the endgame, and converges to a 4.7 s buffer that is still falling at
move 70. 0.050 is deeper than the shipped policy in the opening, gives back
nothing before move 45 and 0.04 ply after it, and halves the wasted reserve from
20.6 s to 10.4 s. Shipped: 0.050.

None of the four flags. Once the clock drops under 3 s the panic branch spends
200 ms against a 500 ms increment, so the clock recovers rather than collapsing.
That is the only reason 0.065 was not an outright hazard.

The honest size of this change: about a quarter of a ply in the opening and a
halving of dead reserve. Not the result the first gate implied.
