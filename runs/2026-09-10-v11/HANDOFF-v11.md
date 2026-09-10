# v11 handoff — Danny's session, night of 9-10 September

Branch `danny-test`, six commits past `fa93635`. Preflight clean: **8 pass, 3 warn,
0 fail.** A 30-game Stockfish 2200 run plus a 40-game A/B started 02:12 BST.

---

## The headline: the engine was losing games on time, and now it isn't

Self-play from the round-14 curated opening, real time control, machine idle:

| | v10 (live build) | v11 |
|---|---|---|
| outcome | **FLAG at ply 156** | reached the **600-ply cap**, drawn |
| clock left | **-0.55 s** | 116.7 s / 117.1 s, minimum 10.5 s |
| worst overshoot | 4.73x budget | **0.85x** |
| plies over budget | many | **0 of 600** |

0.85x is exactly the `budget_ms * 0.85` abort threshold, so the clock policy finally does
what it was written to do. This is the first time anything in this repo has driven a game
to the actual 600-ply draw rule.

### It took two fixes, and the first one alone was not enough

**`qsearch` took `start_time` and `budget_ms` and read neither.** Every deadline check in
the file was outside it (negamax `:202`, driver `:456`/`:497`), so once the search entered
a capture sequence it ran to completion regardless of budget. Measured: 6,061 ms against a
648 ms budget at ply 155.

Adding the check did **not** fix the flag. A clean re-run still flagged at ply 112. The
abort was firing ~23,000 times without stopping the search, because **an aborted child
returns and the parent's move loop immediately starts the next move**. Unwinding a
depth-10 tree cost ~35 moves x 256 nodes per level: 5.8M nodes and 1,951 ms burned *after*
the deadline. The loops now break on the stop flag.

**Third bug found on the way:** the TT store had no timeout guard. On abort `negamax`
returns a fabricated `0.0`, which propagated up as a real child score and was written as
an exact entry — with "always replace", into a table 98% occupied by move 156. Every
timed-out search was poisoning it with fake draws.

---

## What is in v11

    7b41bcc  LMR scaling + history penalty       +0.60 ply (8.20 -> 8.80)
    5fb2495  panic path actually searches        budget use below 3s: 1.2% -> 57%
    d27c6f7  unwind immediately on abort         the flag fix
    73e7509  SEE + skip losing captures          +0.60 ply, +3.9% nodes/sec
    80c013c  qsearch clock + TT abort guard      no measurable cost
    0a39d26  packaging + stale docs

**SEE.** Ordering was MVV-LVA only, so quiescence searched QxP into a defended pawn and
burned nodes proving it was bad. Now skips captures scoring below zero. The tactical
position dropped 856,648 -> 577,599 nodes at the same depth. x-rays fall out of the
algorithm (slider attacks recomputed against live occupancy), and `tests/test_see.py`
checks that **differentially** — the same position with and without a rook behind the
rook, enemy king moved off the target square so the defenders do not balance and mask a
broken loop. A single-value assertion there passes either way; that mistake was made and
caught.

**Panic floor.** Below 3000 ms the driver did `if panic: break` after one iteration, and
because that sat above `completed_depth = depth`, every such move reported depth 0 — the
instrument said "no search" when it had done one ply. It spent 2.4 ms of a 200 ms budget
and played whatever depth 1 liked, so the last seconds of every close game were
near-random. Also softened a 2.7x cliff at the 3000 ms boundary. The move chosen at
2999 ms now agrees with the full search at 3000 ms instead of switching to a different
one.

**LMR + history.** Reduction was a flat 1 ply regardless of depth or move number; now a
log table built at import. History only ever rewarded the cutoff move, so ordering never
learned which quiets were bad; failed quiets are now penalised, clamped to +/-32768
(int32 with `depth*depth` bonuses genuinely can wrap over a long game and invert
ordering).

---

## What was tried and dropped

**PVS — written, failed its gate, reverted.** PVS is exact: same move, same score, fewer
nodes. It gave different scores on four tactical positions. Checked whether that was the
known PVS/TT bound interaction by disabling the TT probe on both sides — it **still**
differed and used **15% more nodes** (1,336,338 -> 1,542,293), the opposite of what PVS
does. That is an implementation bug, not an artefact. Left for whoever picks it up.

The gate is committed as **`tools/fixed_depth_probe.py`** and is worth knowing about:
`tests/test_search_equivalence.py` **cannot test the numba search** — it hooks
`SearchContext.check_time`, `TimeUp` and `tt.clear()`, all `search.py` concepts. The only
equivalence harness in the repo covers the Python fallback, which has not played a rated
game since v10.

**NNUE — confirmed dead, agreed.** Nothing was spent on it.

---

## Research findings that change what is worth doing

**The 8 Void and 1 Illegal games cost us nothing.** Round 32 is the missing Illegal game
and **we won it** — "Won by illegal", `[Result "0-1"]` with us as Black, 61.5 s left, all
20 of our moves legal. The opponent made the illegal move. And the voids cost zero rating:
17+15+20 = 52, 60-52 = 8, exactly the void count, so they are excluded from the record
rather than scored. `unterminated` is documented nowhere — still worth an email.

**The move generator is clean.** 121 perft depths vs python-chess, 0 mismatches, across
Kiwipete, standard 3/4/5/6, ep pins, castling through check, under-promotion. Plus a
full move-set encoding audit over 48 positions, 0 faults, 19 castling and 64 promotion
moves. "The castling encoder is unverified" is closed.

**The opening book is not worth building.** Ceiling is **+0.475 ply** (SE 0.080, n=40) for
a *perfect* book. Ten rated games gave ten distinct start positions, so the curated pool
is at least ~19 and probably hundreds — it cannot be keyed. And we already end games with
**30.9 s unspent** on average, so saved clock has nowhere to go.

**5-man tablebases: no — and the live build probes nothing at all.** `chess.syzygy` is
imported in `search.py` and nowhere else. A runtime counter recorded **0 probes on the
numba path and 57,793 on the Python fallback**. The 35 `.rtbw` files, 1.3 MB, ship and do
nothing. Separately, play-outs show the engine converts **7 of 8** won endings within 2-6
plies of DTZ-optimal *with no tablebase at all*. The one exception is **KBNvK**, which it
cannot win from either start (shuffled 80 and 100 plies).

---

## Corrections to the team docs

`CLAUDE.md`/`AGENTS.md` had five claims the live docs contradict. Two are new and worse
than the three already known:

- **"pondering on their time is allowed" is false.** "Your process is suspended while your
  opponent moves." The file was inviting wasted days.
- **stderr is NOT discarded in rated games.** It is kept, up to 8 KB, in a per-game
  dashboard log carrying init time, per-move time and clock left. That is free
  instrumentation nobody is using.

Plus import budget 60 -> 90 s, six -> ten uploads/day, 300-ply adjudication -> 600-ply
draw. `HANDOFF.md`'s claim that Syzygy is in the evaluation is also corrected.

`harness/rules.py` is stale against the platform (`INIT_BUDGET_S = 60`, `PLY_CAP = 300`
with material adjudication). Not touched — `harness/` is off limits — but it silently caps
any local long-game work at the wrong horizon.

**`weights/karpov.npz` is a trained 768x256x1 NNUE and was the only copy in the repo.** It
was shipping unread in every submission because `package.py` globs all of `weights/`.
Moved to `models/` — tracked, out of the zip. Do not delete it and do not add `*.npz` to
`.gitignore`; that is the mistake that already lost the `.npy` files.

---

## Running now, and how to read it

Started 02:12 BST, `runs/2026-09-10-v11/overnight.log`, per-game lines:

    run 1  v11 vs Stockfish UCI_Elo 2200, 30 games   ~2.4 h
    run 2  v11 vs frozen snapshots/v10, 40 games, real TC  ~3.0 h

Sequential, never concurrent — parallel matches on this Mac poisoned one measurement
earlier in the session and produced a fake 12-second move.

**Read it with these caveats:**

- **+0.60 ply from LMR is not evidence of strength.** Over-reduction raises depth while
  playing worse; that is its failure mode, and depth is the number that would lie to you.
- 30 games vs Stockfish is roughly **+/-90 Elo** — a band, not a point.
- The 40-game A/B has SE ~7.9%, short of the 60-game standard. Interval crossing 50%
  means **unmeasured**, not neutral.
- The A/B likely **understates** v11: the flag bug it fixes bites in long games, and
  self-play from one opening may not produce many.
- If the A/B is negative, the bisect is clean — `7b41bcc` is the only search-behaviour
  change since the last fully verified state. Revert it and keep the flag fix and SEE.

---

## Suggested next, in order

1. **PVS, properly.** `tools/fixed_depth_probe.py` is the gate; make it exact.
2. **Wire a root-only tablebase probe into the numba path**, or drop the 1.3 MB. Shipping
   it unread is the worst of the three options and has been the state since 8 September.
   Root-only costs 165-321 nodes per move against a ~2.5M nodes/sec search. Fixes KBNvK.
3. **`make gate` is red on HEAD** and has nothing to do with v11 — 75 ruff and 5 mypy
   errors in the shipped engine on the locked tool versions, so CI is failing too. Nobody
   had noticed, and it means "the gate passes" is not currently a meaningful statement.
4. **Pull the ~50 newer PGNs.** Every game we have finished 4-6 Sept and v10 went live on
   the 8th, so all of the void/shuffle analysis describes v9 or earlier.
