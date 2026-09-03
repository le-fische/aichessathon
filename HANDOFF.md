# AI Chessathon Agent Handoff

## CURRENT STATE
`v1-philidor` is live on the platform and validated.
Measured: 97.5% win rate vs greedy baseline.
Git tag: `7ac808a`

## INVARIANTS
- Python 3.12 only, never repin.
- Only the five allowed packages (numpy, torch, onnxruntime, numba, python-chess).
- Only `agent.py`, `search.py`, and `evaluation.py` at the repo root; `package.py` sweeps root `.py` files into the zip.
- Never edit `harness/`.
- `make gate` must pass (ruff and mypy strict).
- `get_move` must never raise and must always return a validated legal move.
- No third-party engine code, ever, including as a reference to copy from.
- Stockfish may be used as a local sparring opponent and to annotate training data, but never inside the zip, never imported by the submission, and its source is never read or copied.

## BENCHMARK POSITIONS
Measure node rate and depth using these two closed middlegames (around move 6 to 8) rather than kiwipete, because they are the most branching-heavy cases we actually face:
1. `r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8`
2. `r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6`

## HOW TO VERIFY
1. Fuzzing: `uv run python tests/test_fuzz.py` (Must print "Fuzzing passed 200 FENs")
2. Gate: `make gate` (Must report ruff and mypy clean, and finish both games)
3. Zip size: `make zip` (Must be under 50 MB, preferably just a few files at root)
4. Fast baseline: `uv run python -m harness.arena --opponent baselines/random --games 10`

## TRAPS ALREADY HIT
- The `uv` virtualenv defaulting to 3.14 instead of 3.12 (must use `uv python pin 3.12` and run `make setup`).
- Scratch `.py` scripts left at the repo root got swept into the submission zip by `package.py`.
- The fuzz test being deleted rather than fixed.
- Draws being incorrectly scored as static evaluations instead of zero (a win would blindly walk into stalemate).
- Mate scores not being ply adjusted, causing the agent to shuffle instead of finding the fastest mate.
- `board.is_repetition(3)` being called at every node, devastating performance (now cleanly gated behind `halfmove_clock`).
- Legal moves generated twice per node.

## NEXT UP
`v2-morphy`: Transposition table, followed by MVV-LVA, killers, and history move ordering, followed by quiescence search.
Note that this is currently implemented and stored in the `versions/v2-morphy` archive and on the `wip/v2-tt` branch, waiting to be promoted tomorrow pending the final head-to-head results against `v1-philidor`.

## OPEN ISSUES
- Time check granularity: The longest move reached 92.7% of its budget against an intended 0.85 hard stop. This happens because the clock is only checked every 2048 nodes.
