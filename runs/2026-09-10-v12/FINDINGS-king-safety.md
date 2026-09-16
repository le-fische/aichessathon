# King safety: measured, failed its gate, reverted

## The gate, set before the run

> ship if the 95% lower bound on the score clears 50%

## The result

    snapshots/v12-ks vs snapshots/v12-base, 40 games at the real time control
    +9 =21 -10, score 48.8%
    terminations: checkmate 19, threefold_repetition 21

    SE (draw-adjusted) 5.4%
    95% CI  38.1% .. 59.4%
    Elo     -9   (95% range -84 .. +66)

The lower bound is 38.1%. It does not clear 50%. **Applied literally: king safety is out
of v12.**

## Reading this honestly

The term is **unmeasured, not proven harmful.** A 95% interval spanning 38-59% contains
"useful" and "harmful" alike; 40 games cannot separate them. The point estimate being
slightly negative is not evidence of harm on its own.

But it does fit the arithmetic we already measured. The term costs **-0.40 ply** of search
depth (`runs/2026-09-10-v12/bench-ks-both.json`). A depth ply is worth roughly 15-25 Elo
in this range. So a 30-60 Elo evaluation term bought with 15-25 Elo of depth nets out
near zero -- which is exactly what 48.8% looks like.

## Why it was built, and whether that reasoning survives

It was built because all four rated losses were checkmates (`FINDINGS-losses.md`) and
round 93 in particular sat level on material for 20 moves while the king danger score
climbed 24 -> 139. That diagnosis stands. What does not follow is that *this* term, at
*this* cost, is the fix.

Note also `FINDINGS-r95-correction.md`: on round 95 the term did fire on our own king and
the loss was pawn structure, not king safety. `_pawn_structure` still knows only passed
pawns -- no doubled, isolated or backward pawns. That remains the larger untouched gap.

## The work is kept, not discarded

The implementation is correct and gated: the two evaluations agree on all 7,663 positions
of the random-walk test, and `tests/test_king_safety.py` sign-checks it by hand. It is a
**v13 candidate** once either

1. it gets cheaper -- the depth cost is the problem, not the concept (an incremental
   attack table rather than recomputing per evaluation), or
2. the evaluation around it is strong enough that the term is not paying for itself out
   of depth.

## The revert

    git revert 9d21403   # half 2 -- attacker count
    git revert b5462c9   # half 1 -- pawn shelter and open files

Verified rather than assumed: those were the **only** two commits to touch
`evaluation.py` or `bitboard.py` since the v11 ship (`1bc490d`), so after the revert both
files are byte-identical to the shipped v11:

    evaluation.py  sha256 c7776dff84ad726e...  MATCH
    bitboard.py    sha256 d6bb8861c91cd3f5...  MATCH

`git grep KS_\|king_safety` over HEAD returns nothing.

## What v12 therefore is

v11, byte-for-byte, plus a root Syzygy probe confined to `nsearch.py` and the `.rtbz`
files in `weights/`. `agent.py`, `bitboard.py`, `evaluation.py` and `search.py` are all
unchanged from the build that is playing rated games right now.
