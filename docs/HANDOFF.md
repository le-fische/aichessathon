# HANDOFF

Read this first. It is the seed a fresh chat needs to be useful in this repo.
Last updated 8 September, 07:2x UTC, by the Claude session coordinating the work.

## Where we are right now

- **v10 is LIVE and ACTIVE** on the ladder. Zip sha256 prefix `5eae2f15`, uploaded
  8 Sept 07:26. It is the first build running the numba search.
- Ladder: **1531, rank #212 of 377**, peak 1626, record 17-15-20 over 60 rated rounds.
  That rating predates v10 and has not yet moved.
- Branch: **`nnue`**. Everyone commits here. `v6-alekhine` and `main` are behind.
- **Uploads and rosters lock 11 September 11:00.** The build frozen then plays the
  13-round Swiss that decides the 50 London seats. Ten uploads per team per day.
- The team is currently **"Ladder only"** on the dashboard: the final Swiss requires a
  UK university student on the roster. This is a people problem, not an engine problem,
  and it outranks every technical item here.

## What v10 is

`agent.py` tries the numba search at import and falls back permanently to the pure
Python search on any exception. Both searches share the evaluation logic but not the
file:

    agent.py ──> nsearch.py ──> bitboard.py ──> evaluation.py   (numba path, ships live)
             └─> search.py  ──> evaluation.py                   (fallback path)

**Two evaluations exist and they must agree.** `nsearch` imports `evaluate` from
`bitboard`, NOT from `evaluation.py`. `tests/test_evaluate.py` compares them on 7,663
random-walk positions. It has silently broken twice, both times because a term landed
in one file and not the other. Any evaluation change goes in BOTH files in the same
commit, and the random walk is the gate -- the six curated positions are not enough,
they contain no bishop pair and missed a 50 cp divergence for hours.

Search: negamax + alpha-beta fail-soft, iterative deepening, transposition table,
MVV-LVA + killers + history ordering, quiescence with stand-pat, null-move pruning
(depth-3, zugzwang guard), late move reductions, aspiration windows, check extension
capped at `ply < 2 * root_depth`, and no LMR on a quiet move that gives check.

Evaluation: tapered PeSTO piece-square tables, passed pawns, tapered bishop pair,
`_mate_drive` for bare-king endings. Syzygy WDL for <= 4 pieces (35 files, 1.3 MB).

Measured: **~2.7 M nodes/sec, ~12.4 plies** at the tournament clock, against the Python
search's ~60-90 k nodes/sec and ~8.4 plies.

## Platform constraints (verified against the official docs)

Python 3.12. Five packages only: torch 2.13.0+cpu, numpy 2.5.2, python-chess 1.11.2,
onnxruntime 1.29.0, numba 0.67.0. One core of an AMD EPYC 9V74 @ 2.60 GHz. 2 GB RAM.
No network. Read-only filesystem plus 256 MB `/tmp`. **120 s + 0.5 s** time control.
**90 s init budget** (we use 28.4 s -- numba JIT). **50 MB unzipped** (we use 1.5 MB).
Games drawn at 600 plies. Rated rounds 08:00-22:00 London.

Rules that constrain design, verbatim:
- "Third party engines are prohibited... any port or translation of one. Your moves
  come from code you wrote."
- "Any network you ship is one you trained yourself, and training it on positions an
  existing engine labelled is allowed. Starting from a published chess network is not...
  a database of another engine's moves or evaluations shipped for lookup at runtime is
  an engine, not training data."
- "Opening books and endgame tablebases are permitted as shipped data, and
  chess.polyglot and chess.syzygy are in the base image."
- "Native binaries inside the zip are rejected... Cython does not work here."
- "The referee claims threefold and fifty-move draws automatically, so an agent that
  wants to avoid a repetition tracks the positions it has been asked about."
- "During your own move one thread is fastest."

## File ownership -- one working tree, several chats

All chats share ONE checkout. **A git branch does NOT isolate you**: checking out a
branch moves every chat onto it. Isolation is by file ownership only.

| Files | Owner |
|---|---|
| `search.py` | the coordinating Claude session. Do not edit. |
| `nsearch.py`, `agent.py` | the numba chat |
| `bitboard.py`, `evaluation.py` | the evaluation chat |
| `nnue.py`, `nsearch_nnue.py`, `tools/*nnue*`, `tools/generate_data.py`, `tools/label_data.py` | the NNUE chat |

If you find a file you do not own already changed, leave it and say so.

## House rules, each learned the hard way

1. **Run it, watch it, then say it.** Every number you report is one you watched print.
   Paste literal output -- `git status --short`, `sha256sum`, the actual benchmark
   lines. Three chats have reported work that was on no branch; one reported an NPS
   figure 3.7x the truth.
2. **60 games minimum, with a standard error.** A 4-game A/B has SE ~= +/-25 points.
   If the interval crosses 50%, the change is *unmeasured*, not neutral. Say so.
3. **Pick a gate that can fail.** We once validated a clock policy by measuring depth
   at a given *clock value*. For a policy that only adds time that comparison is
   monotone by construction -- it could not come back negative, so it was not a gate.
   The real question was depth by *move number*. See `runs/2026-09-08-clock/FINDINGS.md`.
4. **Matches run against frozen snapshots, never the working tree.** Copy the engine
   files into `snapshots/<name>/`, run against that, and print the sha256 of every file
   into the results. A mid-match edit to `bitboard.py` has already contaminated one run.
5. **Fixed-node A/B is the wrong instrument for anything that changes search depth.**
   It is right when node counts are identical by construction (an evaluation rewrite).
   It is wrong for time policies, extensions and reductions. Use the real time control.
6. **Diagnostics never ship unguarded.** `harness/package.py` globs every root `*.py`
   into the zip. An `info depth` print left in `get_move` would have run on every move
   of every rated game. It is now behind `CHESSATHON_DEPTH_LOG`, default off.
7. **`runs/` is append-only.** It was deleted once during a tidy-up and is gitignored,
   so nothing was recoverable.
8. **Scratch scripts go in `tools/scratch/`, never the repo root.** Nine were found at
   the root in one morning, all of which would have shipped.

## Testing switches

- `CHESSATHON_REQUIRE_NUMBA=1` -- turns the silent numba fallback into a hard error.
  **Every match and benchmark must set this.** Without it a test can quietly measure
  the Python search against itself; that exact thing happened and produced a bogus
  "numba is no deeper than python" result.
- `CHESSATHON_DEPTH_LOG=1` -- emits `info depth ...` on stderr for depth harvesting.
- `SEARCH_MAX_NODES` -- fixed-node mode for the legacy A/B arena.

## Verification checklist before any upload

Build the zip from a staging directory of `git show HEAD:<file>`, never the working
tree. Members: `agent.py`, `search.py`, `evaluation.py`, `nsearch.py`, `bitboard.py`,
and `weights/`. Then, against the unzipped archive with only the platform's packages:

- `tools/check_root.py` passes
- exactly 5 `.py` files, 0 binaries, unzipped size well under 50 MB
- cold import time (v10: 28.4 s measured by the judge, 90 s budget)
- `agent.USE_NUMBA_SEARCH` resolves True with no environment variable set
- a 128+ ply game: no illegal move, no flag, clock left at the end
- peak RSS (v10: 632 MB, 2048 MB limit)

The platform's own smoke test runs BUILDING -> SMOKE TEST -> ACTIVE and will reject an
init that blows the budget, so ACTIVE is meaningful confirmation.

## Benchmark positions

    opening     r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8
    middlegame  r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6
    sharp       r2q1rk1/pp1bbppp/2np1n2/4p3/2B1P3/2NP1N2/PPPB1PPP/R2Q1RK1 w - - 4 10
    K+R vs K    4R3/8/8/3k1K2/8/8/8/8 w - - 15 83        (must mate, must not repeat)
    eval split  rn2qbn1/p3p3/b2pkp2/4P2r/P2P1PpP/R1p1K1P1/1PPNNR2/2BQ4 w - - 0 27
                (the position where the two evaluations diverged by exactly 50 cp)

## Tools

    tools/run_gate_match.py     60-game match at the real time control, snapshotted
    tools/run_depth_match.py    short match reporting mean completed depth per side
    tools/clocktraj.py          depth by MOVE NUMBER over a long game -- the clock gate
    tools/clocksim.py           self-play game charging real wall time; reproduces the
                                rated-game clock statistics (74.5% used / 35.7 s left)
    tools/clockprobe.py         depth at a given clock value. NOT a gate on its own.
    tools/ab_arena.py           fixed-node A/B. Only for changes that preserve nodes.
    tools/check_root.py         run before every upload

## Open work

- **Horizon fixes gate** -- check extension and the LMR gives-check guard shipped in v10
  before their gate finished, which is backwards. The 60-game match is running; at 16
  games it reads 9.0/16 = 56.2% +/- 12.4%, leaning positive but unmeasured. If it comes
  back negative, roll them out.
- **NNUE** -- 768x256, trained on positions labelled locally by Stockfish 16.1 arm64
  (`baselines/stockfish/`, gitignored, never shipped). Speed is settled: it costs about
  zero plies and is sometimes faster than the classical evaluation. Go/no-go on a
  60-game gate by end of 9 September.
  **Known bug to fix before it can ship:** `tools/train_nnue.py` writes `weights.npy`,
  `biases.npy` and `weights2.npy` to the REPO ROOT, and `nsearch_nnue.py` loads them
  from there. The zip contains only `*.py` and `weights/`, so those files would not be
  in the submission. NNUE weights must live in `weights/`.
- **Opening book** -- we ship none. Permitted, cheap, and pays twice: stronger opening
  moves and clock saved in the phase where the budget is most generous. Unclaimed.
- **5-man tablebases** -- we ship 4-man only and probe at `<= 4` pieces. The full 5-man
  WDL set is ~380 MB, over the cap, but individual endgames could be cherry-picked into
  the 48 MB of headroom. The cost is probe time, not size; needs measuring.

## Version history and what each taught us

    v5   bitboard evaluation replacing piece_map()  2.93x on the function, +26% nps
    v6   mate drive + moves-to-go clock             REGRESSION 1508 -> 1429; the clock
                                                    policy was scored on time remaining
                                                    and never on depth
    v7   rolled the clock back, kept the mate drive recovered to 1531
    v8   repetition tracking                        stopped repeating; did not stop
                                                    accepting draws when better
    v9   clock 0.045 -> 0.050 + spend the increment reserve 20.6 s -> 10.4 s; honestly
                                                    worth about a quarter of a ply
    v10  numba search, bishop pair, check extension 88.3% +/- 3.4% over 60 games against
                                                    v9's search; 12.4 plies vs 8.4
