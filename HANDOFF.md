# Chessathon Agent Status

## CURRENT STATE
Last updated 2026-09-05 07:40 UTC.

**Live on the ladder: v3-steinitz, uploaded as platform "v4", bot name `Steinitz`.**
Rating **1468, rank 132 of 243**, 4W 4D 7L. Round 16 was live at the time of
writing. For calibration, the house bot labelled CCRL 1400 is at 1539 and ladder
#1 is 2164 — we are below the CCRL-1400 house bot.

**Working tree is ahead of the ladder and verified.** Branch `v6-alekhine`,
clean, two new commits:

- `90e13e0` numba jit bitboard move generator plus `tests/test_perft.py`
- `f28504f` bitboard evaluation, CONTEMPT to 0.0, position-only FEN matching

`v7-tal-wip` at `c8c9472` is the restore point for the previous state.

### What is verified, and how
- **Bitboard evaluation is equivalent, not just faster.** Pre-patch build vs
  post-patch, CONTEMPT held at 0.0 in both so evaluation was the only difference,
  depth 6: node counts identical (596,954 / 468,856 / 34,321) and chosen moves
  identical, at 1.20-1.21x speed. Identical node counts are the proof — the tree
  searched did not change.
- **The numba movegen is correct.** `tests/test_perft.py` compares against
  python-chess rather than hardcoded constants. Start position depth 5 =
  4,865,609, Kiwipete depth 4 = 4,085,603, the four benchmark FENs, a pawn
  endgame and a promotion race — all MATCH, at 21-27 Mnps against 0.43-0.50 Mnps
  for python-chess. **~50x on move generation.** JIT warmup 2.293 s of a 90 s
  init budget.
- Fuzz passes 200 FENs. Arena gate game passes. Zip builds at 42,151 unzipped.

### Two open defects
1. **`make gate` is RED.** 71 ruff errors, all in `bitboard.py` (E701/E702
   statement density, one I001), plus I001 in both test files. Assigned to the
   v6-alekhine chat. Nothing here is a correctness problem, but a permanently
   red gate is how the undefined-CONTEMPT NameError got through before.
2. **mypy does not check the engine.** `pyproject.toml` line 37 says
   `files = ["agent.py", "harness"]`, so `search.py`, `evaluation.py` and
   `bitboard.py` are unchecked. This document previously claimed "mypy strict
   clean over all three engine files" — that was false. Assigned to the
   v6-alekhine chat.

### v7-tal: measured twice, and the answer is no both times
`CONTEMPT` was raised from 0 to 30 with no measurement. Instrumented,
`get_draw_score()` is unreachable in normal play — 3 calls in 400,000 nodes at
depth 7, zero across five middlegame positions at shallower budgets, and
loosening threefold to twofold changes nothing. A same-build A/B differing only
in that constant produced byte-identical games. It is now 0.0.

Second, independent check: the one game we drew by threefold repetition
(Rated 14, White vs Rudra) was replayed from the platform PGN. **We were a pawn
down with opposite-coloured bishops and the halfmove clock at 67.** The draw was
the best available result. **Draw avoidance is not the problem, in the tree or at
the root.** Full evidence: `runs/2026-09-05-perf/FINDINGS.md` and its addendum.

### Two facts from the platform match logs
- **Init budget is 90 s and we use 0.5 s of it.** Room for a large numba warmup.
- **Clock discipline is tight.** Round 14 ran 141 moves and finished with 6.0 s
  left of 190.5 s. The 4.5 percent budget fraction is tuned for a ~22 move game
  and we play games of 141. Assigned to the v7-tal chat.

### Depth is still the competitive problem
~58,000 nps before the evaluation patch, depth 6-7 at the tournament control,
EBF ~2.6 (so move ordering is fine — raw speed is not). The numba integration is
the answer and is the largest remaining item. Honest target is a few times
faster end to end, not 50x: movegen was ~30 percent of search time and
evaluation close to half, and the Python-to-numba boundary gets crossed per node.
A few times faster is two or three plies, which is worth more than everything
else on the roadmap combined.

### File ownership while two chats share one checkout
Git branches do NOT isolate the filesystem. There is one working tree.
- v7-tal chat owns `agent.py` and `search.py`.
- v6-alekhine chat owns `bitboard.py`, `tests/`, `tools/`, `docs/`.
`search.py` passes to the v6 chat for numba integration once the time manager
lands.

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
