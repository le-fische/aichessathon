# Relay handoff — 9 September 07:10 UTC

Le is out of Claude credits for 36 hours (back ~10 Sept 19:00 UTC). Danny holds the
critical path. Lock is **11 September 11:00 UTC**, uploads and rosters both.

Live board with shared status and result boxes:
https://claude.ai/code/artifact/2ef324d6-4479-4b0e-b303-d6b32d66ddcb

## The constraint

One Mac, one match at a time. A 60-game gate at the tournament control takes about
**2h50m**, measured on the run that finished this morning. That is ~12 gate slots in
36 hours, and it is the scarce resource. Build in Antigravity *while* a gate runs.
Never two matches at once — that is how the local time-loss numbers got poisoned.

## Where we stand

| Position | Rating |
|---|---|
| Rank 40 overall | 2172 (not a real target) |
| **50th UK-eligible bot** | **2006 — the seat line** |
| Rank 100 overall | 1833 |
| fischer / lefischer | 1693, rank 155 of 410, ~125th eligible |

50 London seats are filled in finishing order of a 13-round Swiss over locked builds,
not by ladder rank. 103 of the 410 entries are "International" and cannot take a seat.

## DO NOT: NNUE is dead, third gate confirms it

Antigravity will suggest wiring the net into `agent.py` and call it the easiest gain.
It is the most damaging change in the repo. Gated three times: 0/60, then 1.0/43, then
this morning **1 point in 57 games**, and that point came from the opponent flagging.
Roughly −600 Elo. The plumbing works; the network never learned a usable evaluation.

## Running order

**0. Close out the NNUE line** (no machine)
Record the final gate number. Close that chat. Delete `weights/weights.npy`,
`weights/biases.npy`, `weights/weights2.npy` — `harness/package.py` ships `weights/`
wholesale, so they are dead payload in every zip. Commit that deletion on its own.

**1. Gate Terms 3 and 4 together** (2h50m)
Rook open file (`0f575b8`) and doubled/isolated pawns (`5197c06`): both committed, both
unmeasured, neither in v10. First run `tests/test_evaluate.py` — the **random walk** is
the gate, not the six curated positions. If it fails, stop; a divergence between the two
evaluations explains more than a missing term. Gate both as one change (separately costs
two slots). Positive → ship both. Negative → split. Crosses 50% → unmeasured, no ship.

**2. Stockfish calibration** (5h40m) — the diagnostic that decides the rest
Every measurement so far has been self-relative. A 12.4-ply engine with tapered PeSTO,
TT, killers, quiescence, null move and LMR should be well above 1693. Play the frozen v10
snapshot against Stockfish with `UCI_LimitStrength true` at 1700 / 1900 / 2100, 24 games
each, colours swapped, 120s+0.5s, **one game at a time**. Convert each score to Elo with
400*log10(S/(1-S)). Also record mean completed depth at moves 10/20/30/40/50/60, after
verifying the depth instrument reports at all (it printed 0.00 in one previous run).
Near 1700 → the eval is genuinely weak, the search work below is worth doing.
Near 2100 → something in the tournament path is broken, worth more than everything else.

**3. Gate SEE** (2h50m)
Move ordering is MVV-LVA only and cannot tell a winning capture from a losing one.
Skip SEE<0 captures in quiescence, order the rest by SEE with MVV-LVA as tiebreak.
Owner chat owns `nsearch.py` and nothing else. Unit tests with hand-known signs,
including an x-ray case, before any match. Measure nps before and after; flag if the
cost exceeds ~15%. Typically +20 to +50 Elo.

**4. Gate the search-efficiency batch** (2h50m) — same chat, same file
- PVS: line 329 searches every non-reduced move with the full window; only the LMR probe
  at line 318 uses a null window. ~+10 to +25.
- History penalty: line 350 only rewards cutoffs; penalise quiets that failed to raise alpha.
- LMR scaling: reduction is a flat 1 ply regardless of depth or move number. Scale both.
Gate at the real time control; fixed-node A/B is the wrong instrument for depth changes.

**5. Gate the opening book** (2h50m)
Permitted explicitly by the rules. Prefer solid, quiet, structurally simple lines — sharp
theory drops us into middlegames a 12-ply search mishandles. Deliver `book.py` and
`weights/book.bin`; the `agent.py` integration patch goes in the PR description, not
applied. Report mean clock remaining at move 20 alongside the score.

**6. Assemble and upload v11** (~40m)
Do not wait for Le. See checklist below.

## Standing rules

- 60 games minimum; score, games and standard error together. Interval crossing 50% means
  *unmeasured*, not neutral. Ship only when the lower bound clears 50%.
- Matches run against frozen snapshots in `snapshots/`, never the working tree, with the
  sha256 of every file printed into the results.
- `CHESSATHON_REQUIRE_NUMBA=1` on every match and benchmark, or the harness silently
  measures Python against itself.
- Isolation is by **file ownership**, not git branch — all chats share one working tree.
- Run it, watch it, then say it. Paste literal output.
- `runs/` is append-only and gitignored.
- `.git/index.lock` cannot be deleted from the device VM:
  `mv .git/index.lock .git/index.lock.stale-$(date +%s)` and retry.

## Before any upload

1. `tools/check_root.py` passes.
2. Exactly 5 `.py` files, 0 binaries, well under 50 MB. Build from `git show HEAD:<file>`,
   never the working tree. Members: agent.py, search.py, evaluation.py, nsearch.py,
   bitboard.py, weights/.
3. `weights/` contains only the Syzygy tables. No stray `.npy`.
4. Cold import under 90s (v10: 28.4s, all numba compilation).
5. `agent.USE_NUMBA_SEARCH` is True with no env var set.
6. A 128-ply game: no illegal move, no flag, clock left at the end.
7. Peak RSS under 2048 MB (v10: 632 MB).
8. Bot name set to the version's chess-legend name.

Uploads are 10 per team per day and the rating needs rated rounds to converge before the
lock, so anything that gates positive should go up the same day rather than waiting 36
hours. Rollback is re-uploading the v10 zip, sha prefix `5eae2f15`.
