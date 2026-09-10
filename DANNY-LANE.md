# DANNY-LANE.md

Context for a Claude Code session working as **Danny** on this repo.
Read `HANDOFF.md` first, then this. Last updated 8 September 2026.

`HANDOFF.md` is the team's shared seed and it is authoritative on architecture,
house rules and file ownership. This file only covers what is specific to Danny's
lane and what has changed or been corrected since HANDOFF was written.

---

## 0. The thing that outranks all engine work

`HANDOFF.md` says, in its own words, that the team is "Ladder only" because the
final Swiss requires a UK university student on the roster, and that this "is a
people problem, not an engine problem, and it outranks every technical item here."

**Danny is a Computer Science with AI student at the University of Liverpool.**
He is the UK student that item is asking for.

Per the terms at aichessathon.com/terms: a team enters final qualification if at
least one member is a UK university student, and "only its UK members may take a
seat at the in-person final." So Danny on the roster unlocks the team's
qualification, and Danny is the one who would sit the London final on 12 September.

**Rosters and uploads lock 11 September 11:00.** If a session is deciding what to
spend Danny's time on, confirming he is on the roster comes before every item below.
It is a dashboard change, not a code change.

---

## 1. Check the clone before trusting it

As of 8 September this checkout had:

- `danny-test`, `main`, `origin/main` and `origin/danny-test` all at `64862b1`
- **no `nnue` branch at all**, local or remote, though `HANDOFF.md` says "Branch:
  `nnue`. Everyone commits here."
- **no `.git/FETCH_HEAD`**, so this clone had never fetched

Run `git fetch --all --prune && git branch -a -v` before anything else and
reconcile against what HANDOFF claims. Do not assume the working tree is the build
that is playing. `HANDOFF.md` records v10 live with zip sha256 prefix `5eae2f15`;
verify that before reasoning about current behaviour.

## 2. Danny's lane

Agreed with le-fische so the two of us do not collide. Danny works on branch
`danny-test` only.

1. Opening book
2. The 8 Void and 1 Illegal rated games
3. A single preflight script
4. Are 5-man tablebases worth it
5. Long-game stress test past `clocksim.py`'s 84-ply cutoff

Item 2 is **done**. See `runs/2026-09-08-voids/FINDINGS.md`. Sections 4 to 7 below
are the corrections and open threads that came out of it.

**Respect the ownership table in HANDOFF.** `search.py` belongs to the coordinating
session and `agent.py` to the numba chat. Danny reports defects in those files; he
does not edit them without saying so first.

## 3. CLAUDE.md and AGENTS.md are stale. Do not trust their numbers.

Both files quote figures that disagree with the live docs at
https://aichessathon.com/docs. Verified 8 September:

| CLAUDE.md / AGENTS.md say | The live docs say |
|---|---|
| import budget 60 s | **90 s** |
| six uploads per team per day | **ten** |
| 300 plies goes to material adjudication | **a game still running at 600 plies is drawn** |

`HANDOFF.md` has the correct numbers. A fresh Claude Code session auto-reads
`CLAUDE.md`, so it will pick up the wrong ones unless told. Fetch the docs page
before relying on any limit.

What both files get right, and what is easy to get wrong the other way: **`print`
is safe.** The runner "moves the protocol onto a private handle and points file
descriptor 1 at stderr before importing your agent", so a stray print cannot
corrupt the protocol. It costs I/O time per move and nothing else.

## 4. What the Void investigation actually found

Full detail in `runs/2026-09-08-voids/FINDINGS.md`. The short version:

- **The Voids are not our bug.** All 8 games: init 0.4 to 0.5 s of 90 s, never
  flagged (6.0 to 67.3 s left), "Nothing written to stderr", no crash, no illegal.
  Round 23 ended in a level middlegame with 67.3 s still on our clock.
- **No game ever repeated a position three times.** Max occurrence count across all
  9 games is 2. A threefold claim is not what ended them.
- **`unterminated` is not a documented termination.** Not in the docs table
  (illegal, crash, flag, init, ply_cap, void). Not a wall-clock cap either, the
  durations ran 170 to 370 s. **This needs an email to hello@aichessathon.com**,
  which the match logs explicitly invite. Do not burn more hours guessing.
- **The Illegal game has still never been seen.** `round-61-nullgambit.pgn` turned
  out to be a clean 1-0 by checkmate, not the Illegal game. Pulling that log is the
  highest-variance item left in Danny's lane.

## 5. Open engine defect: progress evaluation stops at bare kings

`runs/2026-09-05-krk` diagnosed rounds 17 and 21 and shipped `_mate_drive` in v6.
**Do not redo that work.** But `_mate_drive` is gated on `game_phase <= 6` **and**
exactly one side having nothing but a king, so an endgame with material on both
sides gets no progress gradient at all.

Measured 8 September with `tools/replay_voids.py`, replaying round 31 from 10 plies
before the void with the current build at a 1.4 s budget:

    game                       us  them   ->  us  them  quiet  plies  outcome
    round-31-chesstosterone     9     6   ->   9     5     20     30   shuffled, no result

Rounds 6 and 7, which `runs/2026-09-05-krk` lists as never examined, are the same
shape. `CONTEMPT = 0.0`, but that write-up already established contempt is not the
lever: two repetition fixes were built there and neither helped. The defect is a
flat evaluation, not the draw score. v8's lesson in the version history says the
same thing: "stopped repeating; did not stop accepting draws when better."

## 6. Correcting the 5-man tablebase item

`HANDOFF.md` already has this right and Danny's brief had it wrong. Stating it
plainly so nobody re-derives it:

- The full 3-4-5 piece Syzygy set is **378.1 MiB WDL only**, 939.0 MiB with DTZ
  (chessprogramming.org/Syzygy_Bases). The cap is 50 MB unzipped. The full set is
  out on size, and no probe-time measurement is needed to say so.
- Cherry-picking individual 5-man endgames into the 48 MB of headroom is still
  open, and there the cost genuinely is probe time. That is the measurement.

**New, and probably worth more than the 5-man question:** `weights/` holds **35
`.rtbw` files and zero `.rtbz`**. We ship WDL and no DTZ. So `get_evaluation`
returns a flat `20000 - ply` for every winning position: the search learns that it
is winning and gets no gradient toward the win. That is the same "blind to progress"
defect from section 5 arriving by a second route. 4-man DTZ is a few MB against
48 MB of headroom.

## 7. Packaging, for the preflight script

**Resolved 9 September.** `tools/preflight.py` is now the pre-upload gate: it builds
the zip from `git show HEAD:<file>`, then runs 13 checks against the unzipped
archive (root `.py` inventory, module shadowing, native binaries by magic bytes,
unzipped size, imports against the permitted five, dead weights, per-move output,
cold import, peak RSS, a smoke game, worktree-vs-HEAD drift). Each check was
verified to fail on a doctored zip. See `runs/2026-09-09-preflight/FINDINGS.md`.

The other two scripts each keep a narrower job:

- `tools/check_root.py` -- fast subset, root `.py` names and binary extensions.
  Still what `HANDOFF.md`'s checklist names.
- `tools/verify_zip.py` -- rewritten 9 September. It was stale (it asserted the zip
  was exactly `{agent.py, search.py, evaluation.py}`, so it rejected every build
  after v1). It is now a **provenance check**: is a given pre-built zip a current,
  complete copy of HEAD, or of the worktree with `--against worktree`. That is the
  one thing preflight cannot answer, because preflight always builds its own zip
  and so never inspects one you hand it. It deliberately does **not** gate the file
  set -- deriving the expected members from `harness.package`'s own glob would make
  that check tautological, since a scratch `.py` at the root would appear in both
  the glob and the zip and pass. The file set stays with preflight C02.

`check_root.py` checks root `.py` names and binary extensions. It does **not**
check any of:

- the contents of `weights/`
- unzipped size against the 50 MB cap
- imports against the five permitted packages
- whether a shipped weights file is loaded by anything

That last one was live and is now handled, but **not** the way this section
originally proposed. `weights/karpov.npz` (217,956 bytes) is **a trained 768x256x1
int16 NNUE network** -- keys `fc1_w`, `fc1_b`, `fc2_w`, `fc2_b` -- and it is the
only copy in the repo. `nsearch_nnue.py:14` loads `weights.npy`, `biases.npy` and
`weights2.npy` from the CWD instead; those do not exist on disk and `.gitignore`
has `*.npy`, so they were never committable. **Do not delete it, and do not add
`*.npz` to `.gitignore`** -- that repeats the mistake that lost the `.npy` files.

Moved 9 September to `models/karpov.npz`, with `models/README.md` explaining what
it is. `harness/package.py` ships root `*.py` plus `weights/` only, so anything in
`models/` stays in git and out of the zip.

Submission content: was 1,588,504 bytes unzipped; now 1,370,548 bytes, 2.7 percent
of the budget. Note `preflight.py` C07 keeps failing until the move is committed,
because preflight stages from `git show HEAD:` and HEAD still has the file under
`weights/`. That is correct behaviour, not a bug.

One free integrity check worth building in: `agent.py` prints unconditionally on
import (line 19 or 22) and again on the first `get_move` (line 56 or 58). So any
future match log reading "Nothing written to stderr" proves the build that played
is not the build in this tree.

## 8. Opening book: the flagship is smaller than it looks

Every rated game starts from a curated position 6 to 9 moves deep. From the PGN
headers of 9 games alone: King's Indian Classical, Petroff, Sicilian Closed
(twice), Sicilian Sveshnikov, Dutch Stonewall, Nimzo-Indian, Reti.

A Polyglot book keyed on the standard initial position never gets a hit on move 1
of any rated game. A book has to be keyed on the curated positions we actually
observe in our own PGN archive. That is a much smaller job than "the flagship" and
it should be scoped as such before anyone spends a day on `book.py`.

## 9. Tools added in Danny's lane

All under `tools/`, none at the repo root, so `check_root.py` stays green and
nothing ships.

    tools/analyse_voids.py   replays the failed-game PGNs: plies, threefold counts,
                             material, quiet tails
    tools/replay_voids.py    plays the current build from N plies before a void and
                             reports whether it reaches a result
                             env: GAMES, PLIES, BACK, TIME_LEFT_MS
    tools/fen_suite.py       32 adversarial positions, self-validating. Run it
                             directly to check the suite before trusting a result
    tools/probe_agent.py     runs get_move against that suite, checking legality,
                             UCI encoding, crashes and clock overshoot
                             --agent PATH --only TAG --json OUT

Probe results on 8 September, Python path, `USE_NUMBA_SEARCH=0`: legality, encoding
and clock-panic cases all pass. One defect found: **in a position with zero legal
moves `agent.py` returns the string `"e2e4"`** (lines 84 and 133) where `search.py`
correctly returns `"0000"`. The runner should never ask, so it is theoretical, but
it is a fabricated illegal move sitting in the crash handler. `agent.py` is owned by
the numba chat, so this is a report, not a patch.

**Not yet done:** the probe has only exercised the pure-Python fallback. The numba
`nsearch` path is what actually plays rated games and has a hand-written move
generator. Running the suite with `CHESSATHON_REQUIRE_NUMBA=1` is the obvious next
step. No test managed to make the engine castle, so the castling encoder is also
still unverified.

## 10. Local environment notes

- Repo lives at `~/Desktop/AIChessHackathon/aichessathon`. Rated-game logs and PGNs
  are one level up in `~/Desktop/AIChessHackathon/voided-game-logs`.
- `uv run` fails on this machine: it tries to fetch `torch 2.13.0+cpu` and the
  download host is unreachable. For anything that only needs python-chess, use a
  bare venv with `chess==1.11.2` rather than fighting the lockfile.
- Follow HANDOFF house rule 1: run it, watch it, then say it. Paste literal output.
  And house rule 2: 60 games with a standard error, or call the result unmeasured.
