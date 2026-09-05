# Chessathon Agent Status

**A fresh Antigravity chat reads this file first, and nothing else, before it
starts work.** Every version gets its own chat; a chat closes when its version
ships. Long-running chats degrade — both of the long ones on 5 September
reported completed work that did not exist on disk.

Last updated 2026-09-05 09:00 UTC.

## CURRENT STATE

**Live on the ladder: platform v6, bot name `Tal`.** VALID and Active.
Rating **1508, rank 127 of 264**, 5W 5D 7L. Zip sha256 `f61f82c9f6e0...`:

    a3f8f89d7e2be51860e7db9cfa2f0ec616acf5f253d4536bd7086450801e3e93  agent.py
    c3bc532a65faa856f352c2333c03846ec10522aef64235b3d9a9fe9d6914fcc5  search.py
    d2692572400754cae5fee4786059ecf589232b619a3efa1ffa5dd9bf6fcd1ab3  evaluation.py

For calibration: the house bot labelled CCRL 1400 sits at 1539, above us. Ladder
#1 is 2164. We are not going to top this ladder; the ladder only seeds the final
Swiss.

**Rosters lock 11 September, 11:00.** The final Swiss is for teams with a UK
university student on them. The team is one UBC student. Until that changes,
engine work moves ladder position and nothing else.

### What v6 contains, beyond v3-steinitz
- Tapered PeSTO evaluation iterating bitboards instead of `board.piece_map()`.
  Node-identical, ~1.20x nps.
- `CONTEMPT = 0.0`. It was 30.0 and it was unreachable code.
- Basic-mate drive: pushes a lone enemy king to the edge and walks the winning
  king in. Fixes drawn K+R vs K endgames. See `runs/2026-09-05-krk/`.
- Moves-to-go time management, `time_left / max(20, 60 - fullmove) + 250`,
  capped at 80% of the clock, with the old `< 3000 ms` panic branch removed.
- `agent.py` matches on position only, not the full FEN with move counters, and
  restores `traceback.print_exc()` in its blanket except.

### Not shipped yet: the numba engine
`bitboard.py` is a numba-jitted bitboard move generator, perft-verified against
python-chess on 8 positions at **21-27 Mnps against 0.43-0.50 Mnps**, roughly
50x on move generation. JIT warmup 2.29 s of a 90 s init budget. It also carries
a numba copy of `evaluate()` that matches the Python one on 7,663 random
positions.

**It is not imported by the engine and is deliberately excluded from the zip.**
It ships when the search is integrated. Plan: `docs/integration.md`.

## THE NEXT VERSION IS FISCHER

Versions are named after chess legends in the order they dominated. Shipped so
far: Philidor, Morphy, Steinitz, Tal. Lasker, Capablanca, Alekhine and Botvinnik
were skipped, so the sequence resumes at **Fischer**, then Karpov, Kasparov,
Kramnik, Anand, Carlsen.

**Fischer = the numba engine integrated.** Honest target 2.5-3.5x end to end and
+2-3 plies, not 50x: movegen is ~30% of search time and evaluation close to
half, and the Python-to-numba boundary is crossed per node. It ships behind a
JIT-failure fallback flag so a compilation problem on the platform costs nothing.

After Fischer validates on the ladder, the full search port — negamax,
quiescence and the transposition table inside numba — is the next item. That
removes the per-node boundary and puts us in perft's 26 Mnps regime.

**Do not tune evaluation terms** (king safety, mobility, pawn structure) before
Fischer. They are worth little at depth 6-7 and several times more at depth 9-10.

## HARD RULES LEARNED THE EXPENSIVE WAY

**One working tree, and more than one chat in it.** Git branches do not isolate
the filesystem. Run `git status --short` before editing. If a file you do not own
is dirty, another chat is in it right now.

- `agent.py`, `search.py`, `evaluation.py` — the engine chat owns these.
- `bitboard.py`, `tests/`, `tools/`, `docs/` — the numba chat owns these.
- `runs/` — nobody owns it. **Append only. Never delete anything under it.**
  It is gitignored, so a deletion is permanent. Most of it was destroyed once
  already.

**Do not edit a file you do not own, and if you find one already changed, leave
it.** On 5 September a chat applied a patch to `evaluation.py`, verified it,
then reverted it because the file was not its own. That left the tree
inconsistent and nearly shipped an engine with a known defect. When a test fails
because of a file you do not own, report the failure. Do not repair it by
undoing the other side.

**Report only what you have read off disk.** Twice on 5 September a chat
reported completed work — a committed 55x movegen, a landed time policy — that
did not exist in any branch or file. Before saying a change is done, run
`git status --short` and `sha256sum` and paste the literal output. A hash you did
not read from a file is not evidence.

**Nothing but the engine at the repo root.** `harness/package.py` sweeps every
root `*.py` into the submission zip. Scratch scripts written to the root have
been caught six times. Scripts go in `tools/`, output goes in
`runs/<date>-<version>/`. `tools/check_root.py` enforces it and is wired into
`gate` and `zip`.

## MEASUREMENT RULES
- **Fixed-node A/B is mandatory for build-to-build comparison.** Set
  `SEARCH_MAX_NODES`; wall-clock jitter changes completed depth between
  byte-identical builds.
- **A fixed-node harness cannot measure a time policy.** It holds constant the
  one thing the policy changes. Time policies are measured by simulation for
  safety and by real 120 s + 0.5 s games for strength.
- State the control beside every score. Never a bare "depth" — report completed
  iterative-deepening depth and selective depth separately.
- 20 games at 62.5% is about 1.25 sigma. That is not a result.
- The starter baselines are saturated at 100%. Use a previous version.
- Node identity is the right gate for a change that does not touch move
  ordering, and the wrong gate for one that does. A reordering change legitimately
  searches a different tree; assert on the root score instead, and handle ties.

## WHERE THINGS ARE

    agent.py search.py evaluation.py   the submission
    bitboard.py                        numba movegen + evaluation, not yet shipped
    Makefile pyproject.toml uv.lock    build and gate config
    AGENTS.md                          the organisers' brief. Authoritative.
    HANDOFF.md                         this file
    submission.zip                     built by make zip, gitignored

    harness/    the platform's protocol and clock. NEVER edit.
    baselines/  random, greedy, minimax, numba, stockfish. Never packaged.
    versions/   archived versions, each runnable, with about.txt. INDEX.txt lists them.
    tests/      test_fuzz.py (200 positions), test_perft.py, test_evaluate.py
    tools/      check_root.py, verify_zip.py, ab_arena.py, sim_time.py
    runs/       measurement record, by date and version. Gitignored. Append only.
    docs/       IDEAS.md, integration.md

## INVARIANTS
- Python 3.12 only, never repin.
- Only the preinstalled packages: torch (CPU), numpy, python-chess, onnxruntime, numba.
- Only `agent.py`, `search.py`, `evaluation.py`, `bitboard.py` at the root.
- `submission.zip` must byte-match the root files. Rebuild and verify before upload.
- Never edit `harness/`.
- `make gate` must pass. A permanently red gate is how an undefined-constant
  NameError once reached a measurement run.
- `get_move` must never raise and must always return a validated legal move.
- No third-party engine code, ever. Stockfish is allowed as a local sparring
  partner and for annotating training data, never inside the zip.

## HOW TO VERIFY BEFORE SHIPPING
1. `uv run python tests/test_fuzz.py` — 200 positions, zero illegal moves.
2. `uv run python tests/test_perft.py` — 8 positions against python-chess.
3. `uv run python tests/test_evaluate.py` — numba evaluation against Python,
   including a several-thousand-position random walk.
4. `make gate` — check_root, ruff, mypy strict over 12 files, arena game.
5. Real time-controlled games at 120 s + 0.5 s. Check terminations for `flag`
   and `crash`, not just the score.
6. Build the zip from a staging directory holding only the three engine files,
   and confirm each member's sha256 against the repo root before uploading.

## BENCHMARK POSITIONS
Curated openings harvested from platform validation logs.
- r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8
- r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6
- rnbq1rk1/pp2bppp/4pn2/2pp4/2PP4/N4NP1/PP2PPBP/R1BQK2R w KQ - 0 7
- rnbqk1nr/bp3ppp/p7/3p4/P7/1N6/1PP2PPP/R1BQKBNR w KQkq - 2 8

Endgame regression, from the round 17 draw:
- 4R3/8/8/3k1K2/8/8/8/8 w - - 15 83   (K+R vs K, must mate, must not repeat)

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

Null verified: a build against a byte-identical copy scores exactly 50.0%, every
colour-swapped pair a perfect mirror.

**Pick the node budget honestly.** 400,000 nodes is depth 7 and ~5.5 s per move,
about 11 minutes per colour-swapped pair. 100,000 nodes is depth 5 and ~1 s per
move, an acceptable proxy if you say so beside the number. **4,000 nodes is
depth 2 and tells you nothing about the engine that plays on the platform.**

## UNMINED
18 rated games of PGNs and per-game agent logs, of which two have been analysed.
Both analyses found a real defect; round 17 was worth a full point.
`runs/2026-09-05-krk/analyse17.py` replays a game from its PGN and prints the
material trace. **Rounds 6 and 7 are also threefold-repetition draws and have
never been looked at.** This is the cheapest source of real defects we have.
