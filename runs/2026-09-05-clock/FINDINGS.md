# The moves-to-go clock was a regression. Reverted in platform v7.

## What happened

Platform v6 shipped two changes together: the basic-mate drive and a moves-to-go
time policy. It went live around 09:47 UTC. Over rounds 19-25 the ladder went
**1W 2D 4L and the rating fell 1508 -> 1429**.

Seven games is about one sigma, so the result alone proves nothing. What settles
it is the mechanism.

## The measurement

`depth_compare.py` runs both builds' `get_move` at the clock and move-number
points real games actually reach — taken from the match logs, where round 19 ran
55 moves finishing with 34.2 s spare and round 17 ran 75 moves finishing with
15.5 s — and records the completed iterative-deepening depth.

| position | clock | move | v5 depth | v5 s | v6 depth | v6 s | |
|---|---|---|---|---|---|---|---|
| opening | 120,000 | 1 | 7 | 4.27 | 6 | 1.90 | **v6 shallower** |
| opening | 100,000 | 10 | 7 | 4.17 | 6 | 1.91 | **v6 shallower** |
| opening | 80,000 | 20 | 8 | 2.90 | 7 | 1.92 | **v6 shallower** |
| opening | 60,000 | 30 | 8 | 2.64 | 7 | 1.92 | **v6 shallower** |
| opening | 40,000 | 40 | 8 | 1.80 | 8 | 1.92 | equal |
| opening | 20,000 | 55 | 8 | 1.11 | 8 | 1.06 | equal |
| middlegame | 120,000 | 1 | 7 | 4.93 | 6 | 1.94 | **v6 shallower** |
| middlegame | 100,000 | 10 | 7 | 4.17 | 7 | 1.91 | equal |
| middlegame | 80,000 | 20 | 8 | 3.40 | 7 | 1.91 | **v6 shallower** |
| middlegame | 60,000 | 30 | 8 | 2.64 | 7 | 1.91 | **v6 shallower** |
| middlegame | 40,000 | 40 | 7 | 1.44 | 8 | 1.26 | v6 deeper |
| middlegame | 20,000 | 55 | 7 | 1.11 | 8 | 1.06 | v6 deeper |

**v6 was a full ply shallower on 7 of 12 points, and every one of them is in the
first two thirds of the game.** It is deeper only at move 40+ with under 40 s
left, where it matters least. On move one it thought for 1.90 s where v5 thought
for 4.27 s.

## Why the earlier verification missed it

The moves-to-go policy was chosen on a simulation that scored candidates by
**minimum clock remaining across a 150-move game**. By that metric it was clearly
better: minimum 5,138 ms against the old policy's 2,966 ms, and no flag at 1x,
1.25x or 1.5x overspend.

That metric measured the wrong thing. Not flagging is a constraint, not an
objective; **depth is the objective**, and nothing in the simulation looked at
it. A policy that survives the clock comfortably while searching a ply shallower
in the phase that decides games is worse, and the simulation could not see that
by construction.

The lesson generalises: when replacing something that governs how long the
engine thinks, the acceptance test has to include how deep it gets, not only
whether it runs out.

## What shipped instead

Platform **v7**, zip sha256 `8f84a3bfb432...`, bot name Tal:

    a3f8f89d7e2be51860e7db9cfa2f0ec616acf5f253d4536bd7086450801e3e93  agent.py
    e4bb6898c9f3462106747a336bb3cba6512b7d4d4219dad62de775d53c58af5b  search.py
    d2692572400754cae5fee4786059ecf589232b619a3efa1ffa5dd9bf6fcd1ab3  evaluation.py

**v5's clock, v6's mate drive.** The only difference from live v6 is the budget
block in `get_move`.

Verified before upload (`verify_v7.py`):
- depth restored — equal to v5 on 10 of 12 points, the other two timing jitter
- K+R vs K from the centre: checkmate. From round 17's own position: checkmate.
  K+Q vs K: checkmate. The mate drive is intact.
- 60 random positions through `agent.get_move`, zero illegal moves

The repository's `search.py` carries the same budget block plus Fischer's
test-only `root_score` global, so it is behaviourally identical to the shipped
build but not byte-identical.

## Still open

The time policy is not a bad idea, it was a badly measured one. If it is revisited,
the acceptance test is this depth table, not a clock-survival simulation — and
the honest target is more time in the middlegame **without** giving up a ply in
the opening.
