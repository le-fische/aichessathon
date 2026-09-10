# Round 95: two errors of mine, corrected

I claimed round 95 showed king safety failing, and proposed an enemy-queen gate to fix
it. Both halves of that were wrong. Recorded here so nobody builds on it.

## Error 1: I inverted the sign

`king_safety_mg` returns `penalty[BLACK] - penalty[WHITE]`, so a **positive** value means
Black is penalised more. We were Black in r95. The `+66` at move 38 therefore meant the
term **did** flag our king as in danger. I read it as the opposite and reported that the
term would not have helped.

## Error 2: I claimed the phase taper had retired the term. It had not.

Measured through the losing sequence:

    move  raw delta  phase  weight  actual cp   queens on
      20        -34     20    0.83        -28   both
      30          0     20    0.83          0   both
      36         66     20    0.83         55   both
      38         66     19    0.79         52   both
      44        105     14    0.58         61   both
      46        193     10    0.42         80   white only

Phase never dropped below 10 of 24, so the term kept 42-83% of its weight and was
contributing **52-80 cp against us** from move 36 to the mate. It was neither blind nor
retired.

## What r95 actually shows

The danger appears between moves 30 and 36 (delta 0 -> +66) and grows to +193. The term
tracks it correctly the whole way.

The important caveat on reading any of this: **these positions arose in a build with no
king-safety term at all.** Evaluating them retrospectively shows what the term *would
have seen*, not how the game would have gone. With the term live during search, the
engine may never have walked the king to b8 in the first place. So r95 is weak evidence
either way, and certainly not evidence against.

## The enemy-queen gate

Written, then reverted. It skips the king-safety penalty when the opponent has no queen.
That is defensible on its own merits -- king safety without attacking material is mostly
noise, and it correctly stops penalising a king whose attacker has been traded off -- but
I introduced it to fix a problem that did not exist, and it is untested.

It is a v13 candidate with honest justification, not a v12 change. The A/B currently
running tests the un-gated term, and the working tree has been reverted to match the
snapshot being tested.
