# Don't build the opening book. It cannot hit, and a perfect one buys half a ply.

Worked on `danny-test`, 2026-09-09. Reproduce with `tools/scratch/book_fens.py`,
`tools/scratch/book_clockprobe.py`, `tools/scratch/book_worth.py`.
Raw output: `fens.txt`, `clockprobe.txt`, `worth.txt`, `logclock.txt`,
`branching.txt`.

Timings are LOCAL (this Mac, Python 3.13.5, numba path,
`CHESSATHON_REQUIRE_NUMBA=1`). The platform is one core of an AMD EPYC 9V74.

## Headline

Three independent reasons, any one of which is sufficient. **Do not build it.**

1. **We cannot enumerate the pool.** Ten games gave ten distinct start
   positions and zero collisions. The 95% one-sided lower bound on pool size is
   19 roots and a collision is only 50/50 at 69 roots. We have no idea how big
   the set is, and it is not published.
2. **A perfect book buys +0.475 ply** (SE 0.080, n=40 paired probes). That is
   the ceiling, achieved only if the book answers all six of our first moves
   for free.
3. **We already fail to spend the clock we have.** Mean clock left unspent at
   the end of nine rated games: **30.9 s**. Handing back 29 s of opening time
   adds to a surplus, not to depth.

## 1. The book cannot hit

Every rated game starts from a curated position, 11 to 17 plies deep. From all
10 archived games:

    games=10  distinct full FEN=10  distinct pos-key(4 fields)=10
    we move first in 4/10; opponent moves first in 6/10
    we are White in 5/10;  black-to-move in 9/10
    plies: min 11 max 17 mean 13.7   odd 9/10

Ten draws, ten distinct positions, no repeats. Treating the pool as an urn
(birthday problem):

|  pool size N | P(no collision in 10 draws) |
|---|---|
| 10 | 0.0004 |
| 20 | 0.0655 |
| 50 | 0.3817 |
| 100 | 0.6282 |
| 400 | 0.8928 |
| 1000 | 0.9559 |

    one-sided 95% lower bound on pool size N: 19
    pool size at which a collision is 50/50: 69

So the pool is at least ~19 and plausibly in the hundreds. A book keyed on the
standard initial position hits **never**; a book keyed on observed roots covers
at most 10/N of games, and we cannot bound N usefully from above.

**And the branching kills the "just cover what we've seen" fallback.** Mean
legal moves at a curated root is 36.8, and we move second in 6 of 10 games, so
the book must answer whatever the opponent plays:

    stored replies per root, to answer our first 6 moves:
      opponent branching kept to 1 move  ->            6
      opponent branching kept to 2 moves ->          126
      opponent branching kept to 3 moves ->        1,092
      opponent branching kept to 5 moves ->       19,530
      opponent branching 36.8 (full)     -> 2,553,005,227

Times N roots. At a plausible N of 100 and a miserly branching factor of 3,
that is 109,200 curated entries — every one of which needs to be a *good* move
in a position no published book covers, because these roots are bespoke.

## 2. What a hit would be worth

Upper bound on clock saved: the engine's own spend on its first six moves from
the ten real curated roots.

    our first 6 moves cost, mean 28.92 s (sd 1.81, min 26.37, max 30.99)
    as a fraction of the 120 s base clock: 24.1%
    mean completed depth over those moves: 10.90

So a book that answered all six instantly saves ~29 s. What does 29 s buy?
Paired probes on the same ten roots, at clock C and clock C+29 s, using the
shipping budget model `min(0.045*t + 400, 0.25*t)`:

| clock handback | mean depth gain | gained on |
|---|---|---|
| 30s -> 59s | +0.70 ply (sd 0.48) | 7/10 |
| 45s -> 74s | +0.50 ply (sd 0.53) | 5/10 |
| 60s -> 89s | +0.40 ply (sd 0.52) | 4/10 |
| 91s -> 120s | +0.30 ply (sd 0.48) | 3/10 |

    over all 40 paired probes: mean depth gain +0.475 ply, sd 0.51, SE 0.080

**+0.475 ply, for a perfect book.** For comparison, v10's numba search was
worth about 4 plies (8.4 -> 12.4) and v9's entire clock rework was "honestly
worth about a quarter of a ply". A book sits between them, at the cost of
building a curated repertoire for an unknown position set.

Note the gain is *larger* at low clocks (+0.70 at 30 s) than at high ones
(+0.30 at 91 s), because the budget model is proportional. That matters for
section 4.

## 3. The clock we save has nowhere to go

From the nine rated match logs (`logclock.txt`):

| log | date | moves | first 6 | avg | used | left |
|---|---|---|---|---|---|---|
| round-14-rudra | 09.04 | 141 | 20.3 | 1.31 | 184.5 | **6.0** |
| round-17-noob | 09.05 | 75 | 24.0 | 1.89 | 142.0 | 15.5 |
| round-21-ags | 09.05 | 81 | 11.4 | 1.77 | 142.9 | 17.6 |
| round-23-the-good-team | 09.05 | 30 | 11.2 | 2.26 | 67.7 | 67.3 |
| round-31-chesstosterone | 09.06 | 37 | 22.0 | 2.67 | 98.9 | 39.6 |
| round-32-0x88 | 09.06 | 20 | 24.0 | 3.42 | 68.5 | 61.5 |
| round-4-sillycats | 09.04 | 66 | 26.4 | 2.08 | 137.3 | 15.7 |
| round-6-zagreus | 09.04 | 56 | 26.1 | 2.27 | 127.1 | 20.9 |
| round-7-en-passant | 09.04 | 37 | 24.5 | 2.83 | 104.5 | 34.0 |

    mean first-6-move spend over 9 rated games: 21.1 s
    mean clock LEFT UNSPENT at end          : 30.9 s

The engine finishes its games with more time unspent than a perfect book would
save it. Real spend on the first six moves was 21.1 s, not the 28.92 s measured
locally — this machine is slower than the platform, so the local figure
overstates the prize.

## 4. The one argument that survives, and why it still loses

Round 14 is the exception: 141 moves and **6.0 s left**. Long games are tight,
and `runs/2026-09-09-longgame/FINDINGS.md` establishes that the current build
**flags outright at ply 155** in self-play. A book handing back 21-29 s in the
opening is real insurance against that, and section 2 shows the handback is
worth most precisely when the clock is low.

But it is the wrong instrument for that job:

- The flag is caused by quiescence never checking the clock
  (`nsearch.py:110`, `qsearch` takes `start_time` and `budget_ms` and reads
  neither). A 4-line fix removes the failure mode. A book only makes the runway
  longer before hitting it.
- The panic path below 3000 ms spends 2.4 ms of its 200 ms budget and returns
  depth 0. Fixing that recovers far more than +0.475 ply, for far less work.

**Both are cheaper and strictly better than a book.** If the goal is "don't lose
long games on time", fix the clock; if the goal is "be stronger in the opening",
the book buys half a ply against an unknowable position set.

## Recommendation

**Don't build it.** Reallocate to the quiescence clock defect and the panic
floor. If someone insists on revisiting this, the only version worth scoping is
narrow and cheap: cache our own root replies across games — but note module
state does not survive between games, so that would need shipping a
precomputed table, which lands straight back on the coverage problem.

Two prerequisites if it is ever revisited, both cheap:

1. **Pull the other ~50 PGNs off the dashboard.** Ten games is what makes the
   pool unbounded. Fifty games either produces collisions and bounds N, or
   pushes the lower bound past 100 and kills the idea outright. Either is worth
   having and it is a download, not a measurement.
2. Ask the organisers whether the curated set is drawn from a published suite.
   The email about `unterminated` is already going; this costs one more line.

## Not done

- No book was built and no A/B was run. Nothing here is a strength measurement;
  it is a feasibility and ceiling calculation.
- Depth gain is a proxy for strength, not strength itself. +0.475 ply was not
  converted into an Elo estimate, and the 60-game gate the house rules require
  was never reached, because the ceiling calculation made it unnecessary.
- The local-vs-platform gap is real and unquantified: 28.92 s locally against
  21.1 s in real games for the same six moves.
