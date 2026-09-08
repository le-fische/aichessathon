# Measurement session, 2026-09-05 02:30-04:00 UTC

*Rewritten 09:00 UTC after the original was deleted along with most of `runs/`.
Every number below is reproducible from the scripts in this directory.*

Run on the Mac while both Antigravity chats were stopped. Nothing in the live
working tree was edited; measurements ran against throwaway copies.

Measured on Linux aarch64 through the repo's own harness under Python 3.12 with
the pinned dependency set. Absolute nodes/second differ on macOS; the ratios and
the node counts do not.

---

## 1. CONTEMPT was dead code at tournament depth

`CONTEMPT` had been raised from 0 to 30 with no measurement. Instrumented call
counts for `get_draw_score()` in one `search.get_move()` from the opening
benchmark (`depth_probe.py`):

| node budget | depth reached | search time | `get_draw_score` calls |
|---|---|---|---|
| 4,000 | 2 | 0.07 s | 0 |
| 20,000 | 4 | 0.37 s | 0 |
| 100,000 | 5 | 0.98 s | 0 |
| 400,000 | 7 | 5.46 s | **3** |

Three calls in 400,000 nodes; zero across five middlegame positions at shallower
budgets. Loosening `is_repetition(3)` to `is_repetition(2)` changed nothing, so
the threefold requirement is not the gate. The two paths that return a draw
score need conditions a depth-7 tree almost never produces: a genuine
transposition back to an ancestor of the search path, or `halfmove >= 4`
surviving in a subtree where captures and pawn moves keep resetting it.

A same-build A/B differing only in that constant produced byte-identical games.
**Set to 0.0 and shipped that way.** See also `../2026-09-05-krk/FINDINGS.md`,
which shows what the unreachable branch was hiding.

## 2. `board.piece_map()` in `evaluate()` was 48% of search time

`cProfile` over a depth-6 search from the opening benchmark, 32.1 s total
(`profile_probe.py`):

| function | calls | cumulative |
|---|---|---|
| `chess.piece_map` | 577,488 | **15.26 s (48%)** |
| `chess.piece_at` | 16,976,984 | 7.44 s (23%) |
| `chess.scan_reversed` | 33,481,120 | 4.99 s |
| `chess.generate_pseudo_legal_moves` | 2,880,586 | 5.56 s |
| `evaluation.evaluate` | 378,956 | 10.97 s |

`piece_map()` builds a dict and allocates a `Piece` per piece on every call;
those 577k calls produce the 17 million `piece_at` calls. Iterating the
bitboards directly (`board.pawns & board.occupied_co[c]`, scanned with
`chess.scan_reversed`) computes the identical sum with no allocation.

Evaluation alone, 240,000 calls over six positions (`eval_bench.py`):

| | eval/s |
|---|---|
| via `piece_map()` | 125,749 |
| via bitboards | 367,839 |

**2.93x on the function.** End to end, same position, depth 7 (`nps_probe.py`):

| | nodes | time | nps |
|---|---|---|---|
| before | 2,383,881 | 44.60 s | 53,450 |
| after | 2,383,881 | 35.28 s | **67,571** |

**Byte-identical node count** — the tree searched does not change, so this is
pure speed at zero behavioural risk. `verify_eval.py` re-checks it on three
positions and asserts both node counts and chosen moves. Shipped in platform v5.

## 3. Depth is the competitive problem

Nodes to complete each depth, opening benchmark (`ebf_probe.py`):

| depth | nodes | EBF | seconds |
|---|---|---|---|
| 3 | 20,728 | 6.72 | 0.44 |
| 4 | 37,950 | 1.83 | 0.74 |
| 5 | 225,001 | 5.93 | 4.18 |
| 6 | 359,502 | 1.60 | 6.97 |
| 7 | 1,006,035 | 2.80 | 17.32 |
| 8 | 2,394,852 | 2.38 | 43.66 |

Geometric EBF from depth 3 to 7 is about **2.6** — move ordering and pruning are
doing their job. The problem is raw speed: ~58,000 nps in pure Python, giving
**depth 6, occasionally 7** at the tournament control. The house bot labelled
CCRL 1400 sits above us on the ladder, which is consistent with six plies.

Ordered by expected Elo per unit of work:

1. **Bitboard evaluation** (§2). Done, shipped.
2. **numba.** `AGENTS.md` says numba is how Python gets fast here. Jitted movegen
   over a custom bitboard board, warmed at import inside the init budget.
   Largest ceiling, largest project. Now `bitboard.py`.
3. **Incremental evaluation.** Update the tapered PSQT sums on push/pop instead
   of recomputing. Superseded if evaluation moves into numba.

Evaluation-term tuning is worth far less than any of these while the search sees
six plies.

## 4. Round 14: that repetition draw was correct play

The round 14 threefold draw (White vs Rudra) replayed from the platform PGN
(`analyse14.py`, `game14.san`), 282 half-moves:

| half-move | balance | position |
|---|---|---|
| 36 | **+5** | peak — up a rook's worth |
| 40 | 0 | given straight back |
| 200 | -1 | us 1B, them 1B+1P |
| 282 | -1 | `8/8/5K2/3k4/1b1p4/3B4/8/8 b - - 67 150` |

**A pawn down with opposite-coloured bishops and the halfmove clock at 67.** The
repetition rescued half a point from a worse endgame already heading for a
fifty-move draw.

The real story is +5 at half-move 36 evaporating by half-move 40: material won
early and given straight back, which is a depth failure.

**This conclusion was over-generalised at the time** into "draw avoidance is not
the problem, in the tree or at the root". One game was too small a sample.
`../2026-09-05-krk/FINDINGS.md` has the game that disproves it.

## 5. From the platform match logs
- **Init budget is 90 s and we use 0.5 s of it.** Room for a large numba warmup.
- **Clock discipline was tight.** Round 14 ran 141 moves and finished with 6.0 s
  of 190.5 s. The 4.5% budget fraction was tuned for a ~22 move game. Replaced
  in platform v6 by a moves-to-go policy; `sim_newpolicy.py` checks the
  replacement to 150 moves at 1x, 1.25x and 1.5x overspend.

## Reproduce

```bash
cd runs/2026-09-05-perf
uv run python eval_bench.py       # evaluation microbenchmark, asserts equivalence
uv run python verify_eval.py      # node-identity gate on the bitboard evaluation
uv run python ebf_probe.py        # nodes and EBF per depth
uv run python profile_probe.py    # cProfile hotspots
uv run python depth_probe.py      # depth and draw-score calls per node budget
uv run python analyse14.py        # round 14 material trace
uv run python eval_equiv_fuzz.py  # randomised evaluation equivalence
python3 sim_newpolicy.py          # time policy flag safety to 150 moves
```

Some probes expect variant copies under `~/scratch/`; recreate them from
`bitboard-eval.patch` or edit the paths at the top.
