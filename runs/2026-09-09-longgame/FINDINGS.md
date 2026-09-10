# No: the clock policy does not survive a long game. It flags at ply 155.

Worked on `danny-test`, 2026-09-09. Reproduce with `tools/longgame.py`.
Raw output: `run-a-numba-control.log`, `trajectory-numba.csv`.

Engine snapshot measured, `tools/scratch/longgame-snap/`, byte-identical to HEAD:

    7d29bc31396ff3d2819d9dbdb6aa42ac1aa0c72e9a3010a554259167b04c35fa  agent.py
    8db41e93b7d4efbb80fb3f987e1d8aca920ec41829762192a7701fac5dae8a37  search.py
    88d79da47ab3ce15233b2153d522148b7a218e834875f28c0a96a55aeb0b16ee  nsearch.py
    d6bb8861c91cd3f59bd4269b07140144482d87c84f4c72148117b8cf93140149  bitboard.py
    c7776dff84ad726ef99787f7a3efb5acd0ee3d980edf5d590117282b2dbbee99  evaluation.py

    python 3.13.5   chess 1.11.2   CHESSATHON_REQUIRE_NUMBA=1
    numba: white=True black=True   ply cap 600   claim_draw=False
    import + JIT 11.0 s, rss 311 MB

## Headline

**The engine loses on time.** In a self-play game from a realistic curated
opening position, White's clock went to **-545.8 ms at ply 155** and the game
ended `FLAG (white)`. A flag is an automatic loss. This is not a projection or a
simulation artefact — it is a game that ended, and the numba path is the path
that plays rated games.

We never got to observe behaviour at ply 250 or the 600-ply draw rule, because
the engine flags long before it gets there. That is the answer to the question
the task asked.

    ended     : FLAG (white)   plies=156   result=*
      white: clock left   -0.55s   min clock   -0.55s   used 100.3% of 159.0s
      black: clock left    2.69s   min clock    2.19s   used  98.3% of 159.0s
    worst overshoot ratio: 4.73x  at ply 154  used 2997 ms against budget 633 ms

Black survived with 2.69 s. It was one bad quiescence explosion from the same
fate.

## Root cause: quiescence search never checks the clock

`nsearch.py:110` — `qsearch` takes `start_time` and `budget_ms` in its
signature, and passes both down its own recursion at `:177`:

    def qsearch(pieces, colors, state, alpha, beta, ply, path_keys, path_count, start_time, budget_ms, nodes):

**It never reads either one.** `grep -nE 'start_time|budget_ms' nsearch.py`
shows every deadline check in the file, and all three are outside qsearch:

    :202   in negamax        if (curr_time - start_time) * 1000 > budget_ms * 0.85
    :456   in the ID driver  if (curr_time - start_time) * 1000 > budget_ms * 0.85
    :497   in the ID driver  if (curr_time - start_time) * 1000 > budget_ms / 2

So once control enters quiescence, the search runs to completion no matter how
long that takes. `negamax` polls the clock every 256 nodes; `qsearch` polls
never. The budget is computed correctly and then simply not enforced on the one
subtree that can explode.

The fatal move makes the mechanism plain:

    ply 155  white  clock_in 5515.7 ms  budget 648.2 ms  used 6061.5 ms
             ratio 9.35x   nodes 18,178,756   depth 12

18.2 M nodes against a 648 ms budget. At the node rate this machine sustains
that is ~6 s of work committed with no opportunity to abort.

## Why it only shows up in long games

The overshoot is roughly constant in absolute milliseconds — one quiescence
explosion costs a few seconds whenever it happens. The *budget* shrinks with the
clock (`nsearch.py:388`, `budget_ms = min(clock*0.045 + 400, clock*0.25)`). So
the ratio grows without anything new going wrong:

| phase | budget | typical overshoot ratio |
|---|---|---|
| plies 0-20 | 4100-5800 ms | 0.51 - 1.46x |
| plies 40-90 | 1300-2900 ms | 0.54 - 2.39x |
| plies 140-155 | 630-900 ms | 1.14 - **9.35x** |

Early in the game a 3 s quiescence subtree fits inside a 5.8 s budget and is
invisible. At ply 155 the same subtree is nine times the budget and it is a lost
game. **This is exactly why `clocksim.py` stopping at 84 plies hid it**: at ply
84 the worst ratio in this run was 1.08x.

Sparse endgames make it worse, not better. The worst pre-flag overshoot was
4.73x at ply 154 in `8/3k1P2/6K1/4p3/4P3/B7/8/8 b - - 0 86` — a king-and-pawn
position, where captures are few but the quiescence tree is deep and the node
rate is at its highest.

## Second defect: the panic path wastes its own budget

`nsearch.py:383` — below 3000 ms the policy switches to
`budget_ms = min(200.0, time_left_ms * 0.1)` with `panic = True`. Measured
behaviour at small clocks (`tools/scratch/overshoot_probe.py`):

    position     clock   budget     used   ratio   d   move
    middlegame    3000     535m   313.4m    0.59   7   c5d4
    middlegame    2999     200m     2.4m    0.01   0   f8d6
    middlegame    1000     100m     2.3m    0.02   0   f8d6
    middlegame     100      10m     2.2m    0.22   0   f8d6

Two problems, both visible in those four lines:

1. **A one-millisecond cliff.** At 3000 ms it searches to depth 7. At 2999 ms it
   returns depth **0** — not a 1-ply search, the first move off the generator.
2. **The panic budget is 99 percent unused.** It is allowed 200 ms and spends
   2.4 ms. Under 3 s of clock the engine is effectively a random mover, when it
   could comfortably do a 2-3 ply search and still never flag.

At 1 ms and 0 ms of clock it still takes ~2.2 ms and flags. Nothing can be done
about 0 ms; the point is that the engine reaches those states at all.

## What is fine

- **Memory.** Peak RSS 612 MB during import and the first few moves, settling to
  ~385 MB for the rest of the game, against a 2048 MB limit. No growth trend.
- **The repetition counters** in `agent.py` grow linearly and reached 76 and 77
  entries at ply 156. Not a leak.
- **No mid-game fallback.** `fell back to python mid-game: False`. The numba path
  held for the whole game.
- **Budget arithmetic.** The budget line itself is sane and tracks the clock
  correctly. The defect is enforcement, not calculation.

## Worth watching

**TT occupancy reached 98.02% by ply 156** and rises monotonically through the
game (5% at ply 0, 50% at ply 13, 90% at ply 60, 97% at ply 120). It is never
cleared between moves, only between games. At 98% the table is pure replacement
pressure. This was not isolated as a defect here — it needs its own measurement,
because the natural fix (aging or a generation counter) is a search change and
belongs to whoever owns `nsearch.py`.

## Candidate fix, prototyped and NOT applied

`nsearch.py` is owned by the numba chat. The patch is prototyped in
`tools/scratch/longgame-snap-qfix/nsearch.py` and is four lines — the same
cadence and the same deadline `negamax` already uses:

    if (nodes[0] & 255) == 0:
        with objmode(curr_time='float64'):
            curr_time = time.time()
        if (curr_time - start_time) * 1000 > budget_ms * 0.85:
            return alpha

Returning `alpha` on abort is the conservative choice (fail-low, the caller
keeps its existing best). Whoever applies it should confirm that against the
fail-soft convention in the rest of the file.

Suggested second change, separately: raise the panic floor so that under 3 s the
engine does a real shallow search instead of returning depth 0, and soften the
cliff at 3000 ms.

## The gate this needs, and why the obvious one is wrong

House rule 3 says pick a gate that can fail, and house rule 5 says a fixed-node
A/B is the wrong instrument for a time policy. Both apply here, and there is a
third trap specific to this fix: **a strength A/B is not the gate.** Adding a
clock check to quiescence can only reduce search, so a strength match will read
neutral-to-slightly-negative and would argue against shipping it. The thing
being bought is not strength, it is not losing the game on move 78.

The gate is: **N long games to at least 250 plies, counting flags.** Current
build flags. The fix has to flag zero times, and the worst overshoot ratio has
to stay near 1.0 across the whole game rather than growing with move number.
Depth loss is the cost to report alongside it, not the thing being gated.

## Not done

- Only one long game was completed before the session hit a rate limit. **n=1.**
  The flag is real and the mechanism is confirmed by reading the source, but the
  *frequency* is unmeasured — this could be one game in two or one in twenty.
  Repeat the run across several openings and both colours.
- The candidate fix has not been run at all. No before/after numbers exist.
- The pure-Python fallback in `search.py` was not tested for the same defect.
  It has its own time management and could have the same hole.
- `harness/rules.py` is stale (`INIT_BUDGET_S = 60.0`, should be 90;
  `PLY_CAP = 300` with material adjudication, should be 600 and a draw). This
  run bypassed the referee and used its own loop with a 600-ply cap, so the
  result above is unaffected. Reported for the owner of `harness/`; not patched.
