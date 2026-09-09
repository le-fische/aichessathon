# The 8 Void games: not our bug, but they are pointing at one that is

Worked on `danny-test`, 2026-09-08. Source data: `../../../voided-game-logs`
(8 match logs + PGNs, plus round 61 as a control). Reproduce with
`tools/analyse_voids.py` and `tools/replay_voids.py`.

## Headline

The Void games are **not** a move-generation, protocol, clock or crash fault on
our side. Every measurable health signal is clean in all 8. The cheap rating
buy-back that motivated this task is not there.

What the 8 games do share is that our engine had stopped making progress. Two of
them were dead-won endgames. That half is real, and one of the shapes it takes
is **not** fixed by the mate drive shipped in v6.

## Our agent was healthy in all 8

| signal | what the logs say |
|---|---|
| init | 0.4-0.5 s used of a 90 s budget, 0-1 percent, every game |
| clock | never flagged. Left at end: 6.0, 15.5, 15.7, 17.6, 20.9, 34.0, 39.6, 67.3 s |
| stderr | "Nothing written to stderr" in all 5 games where logs were kept |
| termination | no `illegal`, no `crash`, no `flag`, no `init` |

Round 23 is the clearest case. We were Black, 30 moves in, material 25 v 26, a
normal middlegame, **67.3 s still on our clock**, nothing on stderr, and the
game came back unterminated after 170.5 s. Nothing about our side failed.

## No game ever actually repeated a position three times

`tools/analyse_voids.py`. Replaying every PGN and counting positions by
`_transposition_key()`:

- `is_repetition(3)` is **False** in all 9 games.
- The maximum occurrence count of any position, in any game, is **2**.

So a threefold claim is not what ended these games, and our own repetition
detection was not the thing that fired. `can_claim_threefold_repetition()`
returns True only because a legal move existed that *would* have made a third
occurrence.

That said, in **7 of the 8** the final position had already occurred exactly
twice and such a move was available. The games died one ply short of a
repetition. That is a strong pattern and it is the bridge to the next section.

## `unterminated` is not a documented termination

The published table at aichessathon.com/docs lists `illegal`, `crash`, `flag`,
`init`, `ply_cap` and `void` ("both sides failed"). It does not list
`unterminated`. Our games are recorded `Result "*"`, `Termination
"unterminated"`, "Drawn by unterminated".

Game durations were 170.5, 181.9, 208.9, 241.4, 249.5, 288.1, 291.9, 369.6 s,
so it is not a fixed wall-clock cap. Plies were 60 to 282, so it is not the
600-ply `ply_cap` either.

**Action: email hello@aichessathon.com.** The match logs explicitly invite this
("Email hello@aichessathon.com with this file if anything here is unclear"), it
costs one message, and 8 games with no result recorded is worth an answer.
We cannot resolve it from the logs alone and should stop trying.

## Round 61 is not the Illegal game

`round-61-nullgambit.pgn` is `Result "1-0"`, `Termination "checkmate"`. It is a
clean win. **The one Illegal game is still not in the folder and still has not
been looked at.** That is the single highest-variance item left, because an
illegal move is an automatic loss.

## What is actually wrong: the engine cannot finish

Quiet tail = trailing plies with no capture and no pawn move, i.e. pure shuffling.

| game | colour | plies | material us / them | quiet tail |
|---|---|---|---|---|
| round-14-rudra | W | 282 | 3 / 4 | **67** |
| round-4-sillycats | W | 133 | 0 / 1 | 30 |
| round-21-ags | B | 162 | **8 / 0** | 29 |
| round-7-obligatory-en-passant | W | 75 | 14 / 14 | 20 |
| round-6-zagreus | B | 111 | 12 / 15 | 17 |
| round-17-noob | W | 151 | **5 / 0** | 15 |
| round-31-chesstosterone | B | 74 | **9 / 6** | 8 |
| round-23-the-good-team | B | 60 | 25 / 26 | 8 |

Rounds 4, 6, 7 and 14 are positions where a draw was a fair or good result
(round 4 we are facing a pawn on h2 about to promote). Those are fine.

Rounds 17 and 21 were dead won and thrown away. **Both are already diagnosed
and fixed** in `runs/2026-09-05-krk` (the basic-mate drive, shipped in v6). Do
not redo that work.

## New: the v6 mate drive does not cover round 31

`_mate_drive` in `evaluation.py` is gated on `game_phase <= 6` **and** exactly
one side having nothing but a king. Round 31 is a rook-and-pawn endgame with
material on both sides, so it gets no progress gradient at all.

Verified with `tools/replay_voids.py`, starting 10 plies before the void and
letting the current build play both sides at a realistic 1.4 s budget:

```
game                       us  them   ->  us  them  quiet  plies  outcome
round-31-chesstosterone     9     6   ->   9     5     20     30   shuffled, no result  [33s]
```

30 more plies, one pawn won, 20 of 30 plies quiet, still no result. The
rook-endgame shape of this failure is live in today's build. Rounds 6 and 7,
which `runs/2026-09-05-krk` lists as never examined, are the same shape.

Note `CONTEMPT = 0.0`, but the KRK write-up already established contempt is not
the lever: two repetition fixes were built there and neither helped. The
problem is a flat evaluation, not the draw score.

## Tablebases: the answer to "are 5-man worth it" is no, on size alone

- 3-4-5 piece Syzygy is **378.1 MiB WDL only**, 939.0 MiB with DTZ
  (chessprogramming.org/Syzygy_Bases).
- The submission limit is **50 MB unzipped**.

It does not fit. Probe time never becomes the question. That is the measurement,
and it took ten minutes rather than a day.

**The useful finding underneath it:** `weights/` holds **35 `.rtbw` files and
zero `.rtbz`**. We ship WDL and no DTZ. So `get_evaluation` returns a flat
`20000 - ply` for every winning position, which tells the search that it is
winning but gives it **no gradient toward the win**. That is the same "blind to
progress" defect the KRK write-up found, arriving by a second route.

We use 1.59 MB of a 50 MB budget. 4-man DTZ is a few MB. Adding it converts
"this is won" into "this move shortens it" for every 4-man endgame, without
touching the evaluation.

## Opening book: a standard Polyglot book cannot hit

Every rated game starts from a curated position 6 to 9 moves deep. From the
PGN headers of these 9 games alone: King's Indian Classical, Petroff, Sicilian
Closed (twice), Sicilian Sveshnikov, Dutch Stonewall, Nimzo-Indian, Reti.

A book keyed on the standard initial position never gets a hit on move 1 of any
rated game. If a book is built at all it has to be keyed on the curated
positions we actually observe in our own PGN archive, which is a much smaller
job with a much smaller payoff than "the flagship".

## Packaging: three live defects

1. **`weights/karpov.npz`, 217,956 bytes, is still shipping.** It is still
   tracked by git (`git ls-files` lists it), still on disk, and the string
   "karpov" appears in no `.py` file in the repo. Commit dc1fdc4 "drop dead
   weight from the submission" did not remove it, and `package.py` ships all of
   `weights/`, so it has kept riding along.
2. **`tools/verify_zip.py` is stale and gives false assurance.** It asserts the
   zip contains exactly `{agent.py, search.py, evaluation.py}`. A real
   submission contains 7 root `.py` files plus 36 files under `weights/`, so
   this check would reject every valid build. It is not a preflight.
3. **`package.py` globs `root.glob("*.py")`.** Any scratch file left in the
   root ships. This is the failure that was caught by hand once already.

Current submission: 1,588,504 bytes unzipped, 3.2 percent of the budget.

## One free preflight assertion

The docs say the runner "moves the protocol onto a private handle and points
file descriptor 1 at stderr before importing your agent, so `print` is safe".
Stray prints cannot corrupt the protocol. They cost I/O time per move, nothing
more.

Better: `agent.py` prints unconditionally on import (line 19 or 22) and again on
the first `get_move` (line 56 or 58). So **any future match log that says
"Nothing written to stderr" proves the build that played is not the build in
this tree.** That is a free integrity check on every rated game and it costs
one grep.

## Next

1. Pull the Illegal game. It is the only genuinely unexamined failure left.
2. Email the organisers about `unterminated`.
3. Extend progress evaluation to endgames with material on both sides, or ship
   4-man DTZ, or both. Rounds 6, 7 and 31 are the test set.
4. Replace `tools/verify_zip.py` with a real preflight and delete
   `weights/karpov.npz`.
