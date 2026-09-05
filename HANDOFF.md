# Chessathon Agent Status

## CURRENT STATE
Last updated 2026-09-05 04:00 UTC.

**Live on the ladder: v3-steinitz, uploaded as platform "v4", bot name `Steinitz`.**
After round 15 it sits at **rating 1468, rank 132 of 243, 4W 4D 7L** — down from
1519 / rank 109 after round 14. For calibration, the house bot labelled CCRL 1400
is at 1539 and ladder #1 is 2164. We are below the CCRL-1400 house bot.

v3-steinitz contains everything from v2-morphy plus null move pruning, late move
reductions and aspiration windows. Working tree contents beyond that are **v7-tal
work in progress, uncommitted**: repetition detection on the search path and a
`CONTEMPT` constant.

### WARNING: the working tree is shared
The tree is checked out on branch `v6-alekhine` but holds v7-tal's uncommitted
changes to `agent.py` and `search.py`. Git branches do not isolate the
filesystem. **Do not commit from a v6 chat — it will commit v7's work.** Resolve
this before any further branching: either commit v7's changes on a `v7-tal`
branch, or stash them.

### v7-tal: measured twice, and the answer is no both times
`CONTEMPT` was raised from 0 to 30 with no measurement. It has since been
instrumented and **`get_draw_score()` is unreachable in normal play** — 3 calls
in 400,000 nodes at depth 7, zero calls across five middlegame positions at
shallower budgets. The value cannot affect play. **Set `CONTEMPT` back to `0.0`.**
Full evidence, including why loosening threefold to twofold changes nothing:
`runs/2026-09-05-perf/FINDINGS.md`.

Second, independent check: the one game we actually drew by threefold repetition
(Rated 14, White vs Rudra) was replayed from the platform PGN. **We were a pawn
down with opposite-coloured bishops and the halfmove clock at 67.** The draw was
the best available result, not a win thrown away — contempt would have pushed us
to avoid a draw we should want. **Draw avoidance is not the problem. Do not build
it at the root either.** See FINDINGS.md addendum.

Also from that log: **init budget is 90 s and we use 0.5 s of it**, so there is
room for a real numba warmup at import. And clock discipline is tight — that game
ran 141 moves and finished with 6.0 s left of 190.5 s. Check the time manager
against a long game before trusting it.

### The actual bottleneck, with a patch ready
Profiling says `board.piece_map()` inside `evaluate()` is **48% of all search
time**. Iterating the bitboards directly is 2.93x faster on the function and
**+26% nps end to end with a byte-identical node count** — same tree, pure speed.
Patch: `runs/2026-09-05-perf/bitboard-eval.patch`. Apply it, `make gate`, then
confirm the node count is still identical; if it moves, the eval is no longer
equivalent and the patch is wrong.

At the tournament control the engine completes **depth 6, occasionally 7**, at
~58,000 nps. Depth is the competitive problem, not evaluation terms. Priority
order and the numbers behind it are in FINDINGS.md §3.

## MEASUREMENT RULES
- **Fixed-Node Testing is Mandatory for A/B:** We introduced `SEARCH_MAX_NODES` to eliminate OS scheduling jitter. When set (e.g., `SEARCH_MAX_NODES=50000`), the engine strictly bounds node counts instead of wall-time. **You must use this for every build-to-build comparison** so results are deterministic.
- Time-based path (`time.monotonic()`) is preserved for real games and ship checklists exactly as the platform runs it.
- State the time control / node limit beside every score.
- 10 games is +/-10% for a single game of difference. Treat small gaps as noise.
- The starter baselines are saturated: 100% vs random, greedy and minimax. Use Fixed-Node A/B against a previous version for true strength testing.
- Report completed iterative-deepening depth and selective depth separately, never a bare "depth".

## WHERE THINGS ARE

Repo root holds only what ships or builds:
  agent.py search.py evaluation.py   the submission. Nothing else may be a root .py.
  Makefile pyproject.toml uv.lock    build and gate config
  AGENTS.md                          the organisers' brief. Authoritative.
  HANDOFF.md                         this file. What a fresh chat reads first.
  submission.zip                     built by make zip, gitignored

  harness/    the platform's protocol and clock. NEVER edit.
  baselines/  sparring opponents: random, greedy, minimax, numba, stockfish.
              Never packaged, never imported by the submission.
  versions/   one folder per archived version, each a complete runnable copy
              plus about.txt. INDEX.txt lists them. This is the comparison set.
  tests/      test_fuzz.py, the 200-position legality suite.
  tools/      check_root.py, verify_zip.py, measure_version.py and friends.
              tools/scripts/ holds the ad-hoc run scripts from past sessions.
  runs/       archived logs, PGNs and stats, by date and version. Gitignored.
  docs/       the starter's IDEAS.md.

Two rules that keep it navigable:
  Write run output into runs/<date>-<version>/, never into the repo root.
  Measurement and diagnostic scripts live in tools/, never at the root, because
  package.py sweeps every root .py into the submission zip. tools/check_root.py
  enforces this and is wired into both the zip and gate targets.

## INVARIANTS
- Python 3.12 only, never repin.
- Only the five preinstalled packages: torch (CPU), numpy, python-chess, onnxruntime, numba.
- Only `agent.py`, `search.py`, `evaluation.py` at the repo root. `package.py` sweeps root `.py` files into the zip. `tools/check_root.py` enforces this and is wired into `zip` and `gate`.
- `submission.zip` must byte-match the root files. Always rebuild and verify before upload.
- Never edit `harness/`.
- `make gate` must pass: ruff, and mypy strict over `agent.py`, `search.py`, `evaluation.py`.
- `get_move` must never raise and must always return a validated legal move.
- No third-party engine code, ever.

## HOW TO VERIFY
1. `uv run python tests/test_fuzz.py` — 200 positions, zero illegal moves, zero exceptions.
2. `make gate` — ruff clean, mypy strict clean over all three engine files, both games finish.
3. `make play` — real 120s + 0.5s.
4. Fixed-Node A/B against a previous version.
5. `make zip`, then verify the member list is exactly the three engine files and each byte-matches the root.

## BENCHMARK POSITIONS
Real curated openings harvested from platform validation logs.
- r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8
- r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6
- rnbq1rk1/pp2bppp/4pn2/2pp4/2PP4/N4NP1/PP2PPBP/R1BQK2R w KQ - 0 7
- rnbqk1nr/bp3ppp/p7/3p4/P7/1N6/1PP2PPP/R1BQKBNR w KQkq - 2 8

## NEXT UP
In this order. Each step measured separately against the previous baseline.

1. **Set `CONTEMPT = 0.0`** in `search.py`. No measurement needed — it is
   unreachable code, and the one repetition draw we have was the correct result.
   See FINDINGS.md §1 and the addendum. Close v7-tal out; the premise is dead.
2. **Apply `runs/2026-09-05-perf/bitboard-eval.patch`.** Verify with
   `runs/2026-09-05-perf/nps_probe.py` that the node count is unchanged and nps
   is up ~26%. Then `make gate`, `make zip`, upload.
3. **Fix the FEN comparison in `agent.py`.** Compare position only
   (`board_fen()` + turn + castling + ep), not the full FEN with move counters.
   Latent, not live — see FINDINGS.md §4.
4. **Restore `traceback.print_exc()` in `agent.py`'s blanket except.** Debug
   through `harness/play.py`; `harness/arena.py` does not print agent stderr.
5. **Incremental evaluation.** Update the tapered PSQT sums on push/pop instead
   of recomputing. O(pieces) becomes O(1). Largest remaining win inside
   python-chess.
6. **numba.** `AGENTS.md` says numba is how Python gets fast here and the engine
   imports it nowhere. Jitted movegen over a custom bitboard board, warmed at
   import inside the 60 s init budget. Largest ceiling, largest project.

Evaluation-term tuning (king safety, mobility, pawn structure) is worth far less
than any of the above while the search only sees six plies. Do not start there.

## A/B TESTING
Use `tools/ab_arena.py`, not `harness/arena.py`. The latter always starts from
the standard position and only alternates colours, so two deterministic builds
play the same two games however many you request — it cannot A/B anything.

```bash
uv run python tools/ab_arena.py --a . --b versions/v3-steinitz \
    --games 20 --nodes 400000 --out runs/<date>-<version>/ab.jsonl \
    --start 0 --count 2
# repeat with --start 2, 4, 6 ... then:
uv run python tools/ab_arena.py --games 20 --out runs/<date>-<version>/ab.jsonl --summarize
```

Null hypothesis is verified: a build against a byte-identical copy scores exactly
50.0%, every colour-swapped pair a perfect mirror.

**Pick the node budget honestly.** 400,000 nodes is depth 7, ~5.5 s per move,
~11 minutes per game pair. 100,000 nodes is depth 5 and ~1 s per move — an
acceptable proxy if you say so beside the number. **4,000 nodes is depth 2 and
tells you nothing about the engine that plays on the platform.**
