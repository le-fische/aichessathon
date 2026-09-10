# Gate A: doubled/isolated pawns -- FAILED, not shipped

    snapshots/gateA-pawns vs snapshots/gateA-control, 40 games at 120s + 0.5s
    +5 =29 -6, score 48.8%
    SE 4.1%   95% CI 40.6% .. 56.9%
    Elo -9    95% range -66 .. +48
    terminations: threefold_repetition 28, checkmate 11, insufficient_material 1

Ship condition, set before the run: **95% lower bound clears 50%.** It is 40.6%. **FAIL.**

## Read it as unmeasured, not as harmful

72% of the games were drawn. That is what an A/B differing by one small evaluation term
looks like: the two builds share everything else, steer into the same positions and draw.
Le measured the same effect from the other side -- 62.5% threefold in self-play against 17%
against Stockfish.

With draws that frequent, 40 games carry much less information than 40 games normally would.
A 95% interval of 40.6-56.9% contains "useful" and "mildly harmful" alike. The honest
statement is that **this term is not measurable at this sample size**, not that it is bad.

Coincidentally the same 48.8% my king safety scored. Different term, same verdict.

## A bug found on the way, which is worth more than the gate

`tests/test_evaluate.py`'s random walk failed before the gate could run: the two evaluations
diverged by 20 cp. Cause:

    v11 bitboard.py           no FILE_MASKS at all
    king safety patcher adds  FILE_MASKS  line 690, size 8,  indexed by FILE
    pawn commit 5963d9c adds  FILE_MASKS  line 628, size 64, indexed by SQUARE

The king-safety definition is later in the file and wins, so `numba_pawn_structure` indexed
an 8-element array with squares 0..63. **numba does not bounds-check**, so it read out of
bounds silently and returned wrong doubled-pawn scores -- undefined behaviour, not merely a
wrong number.

Invisible until now because the two terms had never been combined.

**Shipping v12 is unaffected**: with king safety alone `FILE_MASKS[f]` is indexed by file,
bounded to 0-7 by `min(max(king_file-1,0),5)+3`. Correct by construction.

Fixed in the candidate by renaming the per-square array to `PAWN_SQ_FILE_MASKS`; the random
walk then matched on all 7,663 positions and the gate ran against a correct build. **The
rename belongs at source** -- any future combination of these terms hits it.

## Consequence

v12 ships without the pawn terms. `5963d9c` stays on `eval-terms-ungated` / `origin/main`
as a v13 candidate; the concept is sound (our `_pawn_structure` still knows only passed
pawns, which was the diagnosed cause of the r95 loss) and cheap. It needs either more games
or a less draw-prone instrument than self-play to resolve.
