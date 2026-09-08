# aichessathon

A chess engine written from scratch in Python for the AI Chessathon, September 2026.
No third-party engine code: the search, the evaluation and the move generation are ours.

**Start with [HANDOFF.md](HANDOFF.md).** It is the working document: current state, how the
pieces fit together, who owns which file, how we decide anything is an improvement, and
the checklist that runs before every upload.

## Layout

    agent.py        entry point the platform imports. Tries the numba search, falls back
                    to the Python search on any exception.
    nsearch.py      numba-compiled search. This is what plays. ~2.7M nodes/sec, ~12 plies.
    bitboard.py     numba move generation and evaluation. nsearch imports evaluate here.
    search.py       pure-Python search. The fallback path, and the reference implementation.
    evaluation.py   pure-Python evaluation. Must agree with bitboard.py exactly.
    weights/        Syzygy tablebases, 4 pieces and under. Ships wholesale in the zip.
    tools/          harnesses. run_gate_match.py is the one that decides things.
    tests/          test_evaluate.py is the important one: it compares the two evaluations
                    on 7,663 positions and has caught two real divergences.
    runs/           append-only record of every measurement. Do not delete.

## Two things that will bite you

**There are two evaluations and they must agree.** `nsearch.py` imports `evaluate` from
`bitboard.py`, not from `evaluation.py`. A term added to one and not the other passes the
curated tests and fails only the random walk. Change both in the same commit.

**Everything at the repo root ships.** `harness/package.py` globs every root `*.py` into the
submission zip, and includes `weights/` wholesale. Scratch scripts go in `tools/scratch/`.

## Measuring

A change is not an improvement until a match says so. 60 games minimum at the real time
control (120s + 0.5s), colours swapped, against a frozen snapshot, reported as score, games
and standard error. If the interval crosses 50% the change is unmeasured, not neutral.

    CHESSATHON_REQUIRE_NUMBA=1 uv run python tools/run_gate_match.py

`CHESSATHON_REQUIRE_NUMBA=1` turns the silent numba fallback into a hard error. Every test
sets it. Without it a match can quietly measure the Python search against itself, which has
already produced one bogus result.
