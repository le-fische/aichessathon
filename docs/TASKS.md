# Tasks for a new collaborator

Everything here is chosen to be **safe to work on in parallel**. Three agent sessions
and one coordinating session are editing this repo continuously, and the main source of
wasted effort so far has been two people touching the same file. Each task below either
creates new files or produces a measurement, so nothing you do can collide with work in
flight.

## Ground rules

Work on your own branch, off the current tip:

    git checkout nnue && git pull
    git checkout -b book        # or whatever the task is

**Do not edit these files.** They are owned and actively changing:
`search.py`, `nsearch.py`, `agent.py`, `bitboard.py`, `evaluation.py`, `nnue.py`.

If a task needs a change in one of them, write the change as a small patch in your
branch's own file and say so in the PR. The coordinating session merges those by hand.

**Everything at the repo root ships** in the submission zip, and `weights/` ships
wholesale. Scratch scripts go in `tools/scratch/`.

**A change is not an improvement until a match says so.** 60 games minimum at the real
time control, colours swapped, against a frozen snapshot. Report score, games and
standard error together. If the interval crosses 50%, the change is *unmeasured*, not
neutral, and saying so is a good result, not a failure.

---

## 1. Opening book  — highest value, fully isolated

We ship no opening book. The engine thinks from scratch on move one, spending up to five
seconds on positions settled a century ago. The rules permit one explicitly: *"Opening
books and endgame tablebases are permitted as shipped data, and chess.polyglot and
chess.syzygy are in the base image."*

It pays twice: book moves are stronger than what a 12-ply search finds in an opening,
and they cost no clock. Our review of 60 rated games found we were being checkmated on
move 43 while still holding 42 seconds, so clock saved early is not a small thing.

**Deliver**
- `book.py` at the repo root: loads a Polyglot book once at import, exposes
  `probe(board) -> Optional[chess.Move]`, returns `None` outside the book.
- `weights/book.bin`: the book itself. Size is not a constraint, we use 1.5 MB of 50 MB.
- `tools/build_book.py` if you generate rather than source it.
- A three-line integration patch for `agent.py`, written in your PR description, not
  applied. Someone else owns that file.

**Design decisions that are the actual work**
- How deep to trust it, and what happens on exit.
- Whether to play the most common move or weight by the book's own scores.
- **Which lines.** This matters more than the plumbing. A book full of sharp theoretical
  lines drops us into middlegames a 12-ply search mishandles, and is worse than no book.
  Prefer solid, quiet, structurally simple positions. Our engine understands material and
  piece placement well and understands long-term compensation badly.

**Done when** 60 games at 120s + 0.5s against the same build without the book, reported
with a standard error, plus the mean clock remaining at move 20 for both sides. The
second number is half the point of the exercise.

---

## 2. Explain the Void and Illegal games — possible real bug

Of our first 60 rated games: 8 came back **Void / "Unterminated"** and 1 terminated as
**"Illegal"**. Nobody has investigated. An illegal move is an automatic loss, so if there
is a move-generation or protocol bug hiding in there it is costing us whole games, and it
would also be by far the cheapest rating we could buy back.

**Deliver** `tools/analyse_failures.py` plus a short findings file in
`runs/<date>-failures/FINDINGS.md`.

**Where to start** The dashboard has a "Download all games" link that returns per-game
metadata as CSV, including terminations and clock statistics. Find out whether PGNs are
retrievable per game. Then: is Void correlated with a colour, a clock state, a specific
opponent, a game length? Does the Illegal game reproduce if you replay the position
through `agent.get_move`?

**Done when** you can say what those 9 games have in common, or demonstrate that they are
platform-side and not ours. Either answer is worth having.

---

## 3. A single pre-upload check script

The same class of mistake keeps nearly shipping. In one morning: nine scratch `.py` files
sitting in the repo root, all of which `harness/package.py` would have globbed into the
zip; a debug `print` to stderr left unguarded inside `get_move`, which would have run on
every move of every rated game; and a 218 KB dead weights file riding along in `weights/`
in every submission for days.

Each was caught by hand. They should be caught by a script.

**Deliver** `tools/preflight.py` that builds the zip from `git show HEAD:<file>` (never
the working tree) and fails loudly on any of:
- repo root contains a `.py` file not on the allow-list, or any binary
- the zip contains anything other than the expected modules and `weights/`
- unzipped size over 50 MB
- cold import time over 60 s, against the 90 s budget
- `agent.USE_NUMBA_SEARCH` is not True with no environment variable set
- a 128-ply self-play game produces an illegal move, a flag, or a crash
- peak RSS over 1.5 GB, against the 2 GB limit
- `tests/test_evaluate.py` fails, including the random walk

**Done when** it passes on the current HEAD and fails on a deliberately broken tree.
This one has no glamour and is probably worth more than any single evaluation term.

---

## 4. Are 5-man tablebases worth it?  — measurement, not code

We ship 4-man Syzygy WDL (35 files, 1.3 MB) and probe at `occupied.bit_count() <= 4`.
The full 5-man WDL set is roughly 380 MB, far over the 50 MB cap, but it is per-endgame
files, so a subset could fit in the 48 MB of headroom. **KRPvKR** — rook and pawn against
rook — is the most common endgame in practical chess and one a 12-ply search handles
badly.

**The cost is probe time, not size.** Syzygy probing hits disk, and at 2.7 M nodes/sec a
probe is enormously expensive relative to a node. Raising the cap to 5 pieces means far
more probe hits deep in the tree, and that could easily cost more node rate than it wins
in accuracy.

**Deliver** a findings file answering: which 5-man endgames fit the budget, what a probe
costs in microseconds, what raising the cap does to node rate on the benchmark positions,
and whether the trade is positive. A well-argued "no" is a real result and saves someone
else the day.

---

## 5. Long-game and flag-safety stress test

The draw rule is 600 plies. Our clock policy has been rewritten twice, and both times the
failure only appeared in long games. The first version left 35 s unspent on average; the
version after it fell to a 4.7 s buffer at move 70 and was still dropping. `tools/clocksim.py`
missed both, because it stops when the self-play game ends, which was 84 plies.

**Deliver** a test that plays to the ply cap, or close to it, and asserts the clock never
crosses a floor. Extend `tools/clocktraj.py` rather than starting over — it already
measures depth by move number, which was the metric that exposed the second bug.

**Done when** we know the engine's behaviour at move 150 and move 250, not just move 70.

---

## Priority

If you only do one, do **1**. If you have a day, do **1** and **3**. Task **2** is the
highest-variance: it might be nothing, or it might be nine games of free rating.
