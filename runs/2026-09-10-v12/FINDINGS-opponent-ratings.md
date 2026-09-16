# v11's rated "collapse" was mostly the strength of the field

Opponent ratings, supplied from the dashboard (as of round 99, not as-played):

    rnd    opp     expected   got    diff
     91   1749       42.0%    1.0   +0.58
     92   1775       38.4%    1.0   +0.62
     93   1900       23.3%    0.0   -0.23
     94   1781       37.6%    1.0   +0.62
     95   1816       33.0%    0.0   -0.33
     96   1900       23.3%    0.0   -0.23
     97   1766       39.6%    0.0   -0.40
     98   1748       42.2%    0.0   -0.42
     99   1700       49.0%    0.5   +0.01

    mean opponent rating   1793
    our rating             1693
    expected score         3.28/9 = 36.5%
    actual score           3.50/9 = 38.9%
    performance rating     1714   (+21 vs our own rating)

## What this overturns

The working story all afternoon was "v10 scored 63.6%, v11 scored 38.9%, something in v11
is broken." The field explains it. v11 played opponents averaging **100 Elo above our own
rating** and scored **2.4 points above** what a 1693 engine should score against them.

Two of the five losses (r93, r96) were to **1900s**, where par is 23%. Those were not
engine failures. Note that the king safety term was built off the r93 loss
(`FINDINGS-losses.md`) -- a loss that, on these numbers, needed no special explanation.
That term then failed its own A/B (`FINDINGS-king-safety.md`), which is consistent.

The genuinely sub-par results are **r97 (1766) and r98 (1748)** -- near-even pairings,
both lost.

## Two caveats, stated because they matter

**1. Circularity.** 1693 is our rating *now*, after these nine games have been absorbed
into it. The correct denominator is our rating going *into* r91. Break-even is **1711**:

    entered r91 rated below 1711 -> v11 met or beat expectation
    entered r91 rated above 1711 -> v11 underperformed by the difference

    our rating   expected   actual    delta
        1650       31.1%    38.9%    +7.8%
        1693       36.5%    38.9%    +2.4%
        1725       40.7%    38.9%    -1.8%
        1750       44.1%    38.9%    -5.2%
        1800       51.1%    38.9%   -12.2%

**Our ladder rating immediately after r90 is the single number that closes this.**

**2. n = 9.** The 95% CI on the performance rating is **1390 .. 1930**. This reframes the
evidence; it does not settle it.

Ratings are as of r99 rather than as-played, so opponents' true strength at the time
differed. The direction of that bias is not determinable from the data we have.

## Consequence for the ship decision

The rated dip no longer needs a mechanism inside the engine, so the suspicion that the
40-game self-play A/B flattered v11's LMR scaling loses its motivating evidence. Set
against a rollback to v10, which would reintroduce a flag bug measured in production (17%
of v10's rated moves over budget, worst 13.5x, one move taking the clock from 17.6 s to
2.0 s in a game that was lost), the decision is:

**Do not roll back. v12 = v11 + Syzygy root probe.**

---

# CORRECTION: we entered r91 rated 1779, not 1693

The dashboard rating history gives **R91 = 1779**. Current 1700, peak 1835, rank #175/441.

Everything above used 1693 -- our rating *after* these nine games had already pulled it
down. That is the circularity this document itself warned about, applied anyway. With the
correct entering rating:

    rnd    opp     expected   got    diff
     91   1749       54.3%    1.0   +0.46
     92   1775       50.6%    1.0   +0.49
     93   1900       33.3%    0.0   -0.33
     94   1781       49.7%    1.0   +0.50
     95   1816       44.7%    0.0   -0.45
     96   1900       33.3%    0.0   -0.33
     97   1766       51.9%    0.0   -0.52
     98   1748       54.4%    0.0   -0.54
     99   1700       61.2%    0.5   -0.11

    mean opponent      1793     the field was only +14 above us, not +100
    expected score     4.33/9 = 48.1%
    actual score       3.50/9 = 38.9%
    shortfall          -0.83 points = -9.3%
    performance rating 1714  vs entering 1779  ->  -65 Elo
    rating actually lost  1779 -> 1700 = -79

**The field-strength explanation does not hold.** v11 played opponents at its own level
and underperformed by 65 Elo on the point estimate.

r97 (1766, par 51.9%) and r98 (1748, par 54.4%) are losses to opponents we were favoured
against. The two 1900s were 33% games, not 23% games.

## But it is still not established

    z = -0.61   (needs |z| > 1.96)

Nine games cannot separate a 65-Elo regression from variance. The LMR-flattery hypothesis
returns as a live hypothesis, not a finding.

## What actually decides it

The external controlled anchor, not the rated ladder. Both builds against Stockfish
UCI_Elo 2100, same openings, same order, same time control. See `v10-anchor-2100.log`.

## Consequence for the ship decision -- unchanged, for a different reason

Not "the dip was the field" (false), but: the dip is not statistically established, the
external anchor does not show v11 weaker, and rolling back to v10 would reintroduce a
production-measured flag bug (17% of v10's rated moves over budget, worst 13.5x, one move
taking the clock 17.6s -> 2.0s in a lost game). Trading a measured harm for an unproven
suspicion is the wrong direction under the standing instruction.
