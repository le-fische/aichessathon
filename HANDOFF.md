# Chessathon Agent Status

## CURRENT STATE
We are working through a curated roadmap of classical chess engine features. v2-morphy is complete and live. v3-steinitz is next.

### LIVE DEPLOYMENT
**`versions/v2-morphy` is the live, verified build on the ladder.**
It contains: transposition table, MVV-LVA, killers, history, quiescence, `_transposition_key` hashing, and `generate_legal_captures`. It does NOT contain repetition/contempt logic.

The verified SHAs for `submission.zip` matching `v2-morphy` exactly are:
```
95fb3ef22936d7de3c471305994f503607997f299b07c58f9f9dc74ce80918ae  agent.py
f3f7747521d757e595946c8a11f2b8e8b7f85cd4be53e90ba40ce3b28b83be74  search.py
aedfc00e17ee8c8f68565a2f2a3208536eb2eaeb29aa600b1b167554ba4b3198  evaluation.py
```
*(Uploads used: 3 of 6 on Sept 3)*

### REPETITION & CONTEMPT (Parked in `v7-tal`)
We briefly worked on threefold repetition avoidance and contempt, but pulled v7's scope forward into v2 by mistake. That work is now parked on the `v7-tal` branch (with detailed findings in `v7_notes.md`).
Key lessons learned:
- `search.get_move` builds the board from a FEN, meaning the search is structurally blind to game history and cannot detect repetitions that occurred before the search began.
- Fixing this requires passing a `collections.Counter` of history from `agent.py`.
- The apparent regression in our contempt test was **entirely due to OS scheduling jitter**, not move selection logic. Because the iterative deepening loop used `time.monotonic()`, microsecond differences caused engines to diverge into different depths (e.g. depth 5 vs 6) and play different games. Over a small sample of 5 games, statistical variance looked like a regression. Move selection was proven to be 100% identical across 55 test positions.

## MEASUREMENT RULES
- **Fixed-Node Testing is Mandatory for A/B:** We introduced `SEARCH_MAX_NODES` to eliminate OS scheduling jitter. When set (e.g., `SEARCH_MAX_NODES=50000`), the engine strictly bounds node counts instead of wall-time. **You must use this for every build-to-build comparison** so results are deterministic.
- Time-based path (`time.monotonic()`) is preserved for real games and ship checklists exactly as the platform runs it.
- State the time control / node limit beside every score.
- 10 games is +/-10% for a single game of difference. Treat small gaps as noise.
- The starter baselines are saturated: 100% vs random, greedy and minimax. Use Fixed-Node A/B against a previous version for true strength testing.
- Report completed iterative-deepening depth and selective depth separately, never a bare "depth".

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

## NEXT UP: v3-steinitz
**This conversation is closed. Start a fresh conversation for v3-steinitz.**
1. **Null Move Pruning**: Build and measure deterministically using `SEARCH_MAX_NODES`.
2. **Late Move Reductions (LMR)**: Build and measure deterministically.
3. **Aspiration Windows**: Build and measure deterministically.
Each feature must be built and measured separately against the previous baseline.
