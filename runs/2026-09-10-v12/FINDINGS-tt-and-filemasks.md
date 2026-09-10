# Two negative results and one real bug, 10 Sept evening

## 1. Depth-preferred TT replacement does nothing measurable — not shipped

Le ranked this first, reasoning from an EBF of 4.6-7.0 and 99.71% table occupancy.

**Measured with `tools/tt_replay.py`**, which replays real PGNs, searches *every* ply so
the table fills as it does in a game, and compares both policies on identical positions at
fixed depth 10. `tools/bench_v11.py` cannot measure this at all: it calls `clear_tt()`
before every position, so its searches touch 3.7-7.0% of a 16.7M-entry table and nothing is
ever evicted.

    OCCUPANCY > 95% -- the real-game regime, n = 340 paired positions
      total nodes       -3.6%   (favours depth-preferred)
      per-position      149 better / 169 worse   sign test p = 0.88
      geometric mean   +10.65%  (favours always-replace)   t = +1.09
      95% CI on nodes   -7.8% .. +32.7%
      depth equivalent  -0.086 ply

The total and the geometric mean point in **opposite directions**, which is the signature
of a few huge positions dominating the sum. The robust statistic is the per-position sign
test, and at 149/169 it is a coin flip marginally favouring the current policy.

340 paired samples would comfortably detect a real 5% node change. Nothing is there.
`335064f` stays reverted.

### What was right and what was not, in Le's reasoning

**Right, and stronger than he stated.** The table is not 99.71% full by ply 280 — modelling
cumulative stores against 16.7M slots, the first move alone uses 9.5M nodes and the table is
**~99% full by ply 8 of every game**. Saturation is the normal operating condition.

**Not supported.** That saturation does not translate into fewer nodes when the policy is
fixed. The premise held; the remedy did not.

**And one argument of mine was invalid.** I offered "in-game EBF *improves* as the table
fills" (depth 11: 4.27 early vs 3.69 late) as a counter. Both groups were at ~100%
occupancy — the table saturates by ply 8 — so that comparison comes from endgame material,
not table state. It tests nothing either way. Withdrawn.

## 2. Our EBF was overstated — corrected

`tools/bench_v11.py` passes `--ms` as the engine's **`time_left_ms`**, not as the search
budget, so `numba_search` computed `min(3000*0.045+400, 3000*0.25) = 535 ms` and aborted at
85% of it. Those "3-second" benchmarks ran **0.29-0.45 s**, and EBF is inflated on a
truncated search because the shallow iterations dominate.

    source                          depth      EBF
    bench_v11.py (0.29-0.45 s)       7-9    4.64-7.01   <- artefact, do not cite
    real games (299 plies)          11-15    3.23 mean

The search is **mediocre, not broken**. Closing 3.23 -> 2.5 is worth ~+3 ply, not the +6-8
first claimed. Pruning keeps its rank as the largest lever; the magnitude was wrong.

## 3. A real bug: FILE_MASKS collides between two of Le's own changes

Found by `tests/test_evaluate.py`'s random walk, which failed with a 20 cp divergence
between the two evaluations.

    v11 bitboard.py           no FILE_MASKS at all
    king safety patcher adds  FILE_MASKS  line 690, size 8,  indexed by FILE
    pawn patch 5963d9c adds   FILE_MASKS  line 628, size 64, indexed by SQUARE

The king-safety definition is later in the file and wins, so `numba_pawn_structure` indexes
an **8-element array with squares 0..63**. numba does not bounds-check, so this reads out of
bounds silently and returns wrong doubled-pawn scores. It is undefined behaviour, not just
a wrong number.

Invisible until now because the two terms had never been combined.

**Shipping v12 is unaffected.** With king safety alone, `FILE_MASKS[f]` is indexed by file,
bounded to 0-7 by `min(max(king_file-1,0),5)+3` against the 8-element array. Correct by
construction. The collision requires the pawn patch.

Fixed in the gate candidate by renaming the per-square array to `PAWN_SQ_FILE_MASKS`;
random walk then matched on all 7,663 positions. **Le should apply the rename at source**,
because any future combination of his terms hits this.

## 4. tools/longgame.py was silently testing v10

`LG_SNAP` defaulted to `tools/scratch/longgame-snap`, a leftover v10 freeze
(`nsearch.py 88d79da4`, no v11 flag fix). Every run without an explicit `LG_SNAP` measured
v10. It produced 43.7% of moves over budget, a 6.15x worst overshoot and an outright FLAG,
which reads as a catastrophic regression in whatever build you thought you were testing.

Default now points at the working tree (`ab8d411`). The tool does print the snapshot path
and a sha256 per file — read the banner.

**Useful by-product:** an independent reproduction of the v10 flag bug. v10 flagged; v12 on
the same test was clean at **0.85x worst, 0 of 133 plies over budget**. The Stockfish anchor
where v10 scored 93.8% cannot see this, because it runs on hardware fast enough to absorb
the overshoot.

## 5. Both gate tools had stale copies of the engine's budget

`longgame.numba_budget_ms` still had v10's panic branch AND 0.045; `panic_sweep.budget_of`
had 0.045. A stale copy does not merely mislabel a column — it changes the pass/fail verdict
of the gate meant to catch flags. Both resynced with a comment that they must move together.
