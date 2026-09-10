# AI Chessathon — the competition, verified 9 September 2026

Every page below was fetched **9 September 2026, ~14:04 UTC**. Where the site serves raw
Markdown I pulled it with `curl` rather than a summarising fetcher, so the quotes here are the
literal bytes the site served.

Pages fetched (the sitemap at `https://aichessathon.com/sitemap.xml` lists exactly nine URLs and
I fetched all of them):

| URL | Fetched | Notes |
|---|---|---|
| https://aichessathon.com/docs | 9 Sep 2026 | the rendered participant docs; contains the failure table |
| https://aichessathon.com/docs/agent-contract.md | 9 Sep 2026 | raw; `last-modified: Wed, 09 Sep 2026 00:14:42 GMT` |
| https://aichessathon.com/docs/rules.md | 9 Sep 2026 | raw; `last-modified: Wed, 09 Sep 2026 00:14:42 GMT` |
| https://aichessathon.com/terms | 9 Sep 2026 | page stamps itself `Competition · 2026-08-31.v3` |
| https://aichessathon.com/ | 9 Sep 2026 | carries the only FAQ on the site (section `07 · FAQ`) |
| https://aichessathon.com/leaderboard | 9 Sep 2026 | live ladder; no glossary, no termination list |
| https://aichessathon.com/archive | 9 Sep 2026 | empty until after the event |
| https://aichessathon.com/privacy | 9 Sep 2026 | nothing competition-relevant |
| https://aichessathon.com/daily | 9 Sep 2026 | redirects to sign-in when signed out |
| https://github.com/advitrocks9/aichessathon-starter | 9 Sep 2026 | starter repo README, linked from `/docs` |

`robots.txt` disallows `/api/`, `/admin`, `/dashboard`, `/auth`, `/join`, `/signin`. There is no
public changelog, no separate FAQ page, no dashboard docs and no leaderboard glossary. The only
FAQ is the six-question block on the home page.

---

## 1. Contradictions table — read this first

### 1a. Where `CLAUDE.md` / `AGENTS.md` (they are the same symlinked file) is WRONG

| `CLAUDE.md` says | Live docs say (9 Sep 2026) | Severity |
|---|---|---|
| "Import time has a **60 second** budget" | **90 s.** "The 90s init budget covers importing your agent and runs before the clock starts" — /docs/agent-contract.md | stale, harmless (we under-use it) |
| "**Six** uploads per team per day" | **Ten.** "Ten uploads per team per day." — /docs/agent-contract.md; "10 uploads per team per day" — /docs, /docs/rules.md | stale |
| "**300 plies** without a result goes to **material adjudication**" | **600 plies, and it is a draw.** "A game still running at 600 plies is a draw. The opening position counts toward the 600." — /docs/agent-contract.md | stale, and it changes endgame policy |
| "The process **keeps its core while the opponent thinks, so pondering on their time is allowed**" | **False. Pondering is impossible.** "Your process is suspended while your opponent moves, so work you leave running between your own moves does not run and each side has the core to itself while it thinks." — /docs/agent-contract.md. Same wording in /docs/rules.md under `Pondering`. | **HIGH — this one could waste engineering days** |
| stderr/stdout "is **discarded in rated games** and shown in the validation log" | **Kept in rated games too.** "Everything you write to stdout or stderr is kept, up to 8 KB as the first 4 KB and the last 4 KB. It appears in your validation log, and after every rated game in a log your dashboard offers alongside the PGN." — /docs/agent-contract.md | wrong, and it is a source of free diagnostics we are not using |
| (not mentioned) | "The referee claims threefold and fifty-move draws **automatically**, so an agent that wants to avoid a repetition tracks the positions it has been asked about." — /docs/agent-contract.md | omission |
| (not mentioned) | Process limit is **128**. "Processes | 128. On one core, threads past the first cost you time" — /docs | omission |
| (not mentioned) | "Every starting position is **close to level**." — /docs/agent-contract.md | omission |
| "torch 2.13 (CPU), numpy 2.5, python-chess 1.11, onnxruntime 1.29 and numba 0.67" | exact pins are `torch 2.13.0+cpu`, `numpy 2.5.2`, `python-chess 1.11.2`, `onnxruntime 1.29.0`, `numba 0.67.0` — /docs | imprecise only |
| (not mentioned) | Opening books and endgame tablebases are **explicitly permitted** as shipped data, and `chess.polyglot` / `chess.syzygy` are in the base image — /docs, /docs/rules.md | omission that matters right now |

### 1b. `HANDOFF.md` — everything it asserts checks out, but it is incomplete

| `HANDOFF.md` says | Verdict |
|---|---|
| "Uploads and rosters lock 11 September 11:00" | **Correct.** "Upload close \| Sep 11 11:00"; "Teams \| 1-3 people, one team per person. Creating, joining and leaving a team close Sep 11 11:00" — /docs/rules.md. *Time zone is not stated anywhere — see §3.* |
| "Ten uploads per team per day" | **Correct.** |
| "13-round Swiss decides the 50 London seats", final 12 September | **Correct**, but incomplete: seats are **one per UK member and at most 2 per team**, and there are also Daily Five wildcard seats outside the bracket. See §3 and §4. |
| "90 s init budget", "50 MB unzipped", "120 s + 0.5 s", "600 plies drawn", the EPYC 9V74 spec, the five package pins | **All correct.** |
| "Rated rounds 08:00-22:00 **London**" | Hours correct; **"London" is an inference.** No page states a time zone for the rated rounds. See §3. |
| "The team is currently 'Ladder only': the final Swiss requires a UK university student on the roster" | **Correct.** Exact wording in §4. |

### 1c. `harness/rules.py` disagrees with the platform (I did not change it)

`harness/rules.py` — the file `CLAUDE.md` forbids editing because it "mirrors the platform's
protocol and clock" — currently reads:

```
INIT_BUDGET_S = 60.0
PLY_CAP = 300
```

and `harness/referee.py` at the cap does `return _outcome(board, _adjudicate(board), "adjudication")`,
i.e. **material adjudication at 300 plies**. The platform does **a draw at 600 plies** and gives a
**90 s** init budget. So local long-game results are not honest about the endgame, and the harness
is stricter than the platform on init. Flagging only; another agent owns that file.

### 1d. Did anything change between 8 and 9 September?

Both raw Markdown docs carry `last-modified: Wed, 09 Sep 2026 00:14:42 GMT`, so the files **were
rewritten overnight**. I have no 8 September byte-copy to diff against, so I cannot say what
changed. What I *can* say is that all three items the previous session flagged still read the same
today as they did on 8 September:

- init budget **90 s** — unchanged
- **ten** uploads per team per day — unchanged
- **600 plies → draw** — unchanged

`/terms` still stamps itself `2026-08-31.v3`, so the competition framework has not been reversioned
since 31 August. **No headline change since 8 September has been found.**

---

## 2. Hard limits, each with its source

### Clock and compute

| Limit | Value | Source |
|---|---|---|
| Time control | 120 s base + 0.5 s per move, per side, **wall time** | /docs ("Time control \| 120s per side, plus 0.5s per move"); /docs/agent-contract.md ("The clock is 120s base plus 0.5s per move, per side, enforced on wall time by the runner") |
| Init budget | **90 s**, before the clock starts | /docs ("Init budget \| 90s before the clock starts"); /docs/agent-contract.md |
| Where deferred work is charged | your match clock | "work you defer to your first `get_move` comes out of your match clock instead" — /docs/agent-contract.md |
| CPU | one core of an **AMD EPYC 9V74 at 2.60 GHz**, yours alone while you think | /docs; /docs/rules.md |
| Memory | **2 GB** | /docs |
| GPU | none | /docs |
| Network | **none, in either direction** | /docs. "No network means no hosted inference and no engine APIs, by construction." |
| Processes | **128** | /docs |
| Threads | one is fastest | "During your own move one thread is fastest, since threads past the first share the single core and cost you time." — /docs/agent-contract.md |
| Filesystem | read-only + **256 MB at `/tmp`** | /docs |
| `/tmp` semantics | "It starts empty for every game and is deleted with it, so it is scratch space, **not a cache between games**" | /docs |
| Cache env vars | "`HOME`, `TORCH_HOME`, `HF_HOME` and the other cache paths already point there" | /docs/agent-contract.md |
| Hardware fairness | identical for every game; **both agents on one machine**, taking the core in turns | /docs, /docs/agent-contract.md |

### Submission

| Limit | Value | Source |
|---|---|---|
| Zip size | **≤ 50 MB unzipped** | /docs ("Size \| 50 MB unzipped"); /docs/rules.md; /docs/agent-contract.md |
| Zipped size | **not documented** — only the unzipped figure is given anywhere | — |
| Uploads | **10 per team per day** | /docs, /docs/rules.md, /docs/agent-contract.md |
| Which build plays | "your latest submission that passed validation" | /docs |
| Layout | `agent.py` at the archive root, not in a folder | "A zip without `agent.py` at its root is rejected." — /docs/agent-contract.md |
| Max move reply | **4 KB** | "a move payload over 4 KB … loses that game" — /docs/agent-contract.md |
| stdout/stderr capture | **8 KB kept, as the first 4 KB and the last 4 KB** | /docs, /docs/agent-contract.md |
| Uploads close | **11 September 11:00** | /docs; /docs/rules.md; /docs/agent-contract.md |

### Environment

Verbatim, /docs:

> The environment is fixed. The container ships Python 3.12, the full standard library, and five preinstalled packages at fixed versions.
>
> ```
> torch 2.13.0+cpu     numpy 2.5.2      python-chess 1.11.2
> onnxruntime 1.29.0   numba 0.67.0
> ```
>
> Nothing installs at validation and a requirements.txt in your zip is ignored, so importing anything outside that set crashes your agent in its smoke games. Ask at hello@aichessathon.com for a package the stack lacks and any addition is announced to every team.

**Python 3.12.** Five packages, exactly those pins, plus the full standard library. Nothing else.
`chess.polyglot` and `chess.syzygy` are explicitly called out as present in the base image (/docs).

### Wire protocol

Request, one JSON line per move:

```json
{"fen": "rnbqkbnr/...", "time_left_ms": 87500}
```

Response, one JSON line:

```json
{"move": "e2e4"}
```

- "your colour \| the side to move in the fen"
- "time_left_ms \| your clock before this move. **The increment lands after you move**"
- "malformed output \| counts as an illegal move, which loses the game"

(/docs, Wire protocol table.) `print` is safe: "The runner moves the protocol onto a private handle
and points file descriptor 1 at stderr before importing your agent" (/docs).

---

## 3. Termination table and what each scores

### The published table, verbatim from /docs, section "Failure reference"

| Termination | Cause | Result |
|---|---|---|
| `illegal` | illegal or malformed move | loss |
| `crash` | your process exited, threw, or ran out of memory | loss |
| `flag` | clock ran out mid-game | loss, or a draw when the other side cannot mate |
| `init` | no ready line within the 90s init budget | loss |
| `ply_cap` | the game reached 600 plies | draw |
| `void` | both sides failed | no result recorded |

That is the **complete** table. There are six rows and no others.

The prose in /docs/agent-contract.md, "Failure Semantics", says the same thing:

> An illegal move, malformed output, a move payload over 4 KB, a crash, running out of memory or missing the init budget loses that game. A flag fall loses too, unless the other side has no way to mate, and then the game is a draw. If both sides fail the game is void. There are no retries within a game.

And /docs/rules.md, row `Game end`:

> an illegal move, a crash or missing the init budget loses. Losing on time loses unless the other side has no way to mate, which draws. Both sides failing voids the game. FIDE draw rules apply. A game still running at 600 plies is drawn, and the opening position counts toward those 600

Normal (non-failure) endings are not in this table because they are not failures. /docs/rules.md:
"FIDE draw rules apply"; /docs/agent-contract.md: "Draws follow FIDE rules through python-chess,
which covers stalemate, threefold repetition, the fifty move rule and insufficient material" and
"The referee claims threefold and fifty-move draws automatically."

### `void` — CONFIRMED

The docs define `void` exactly as the team believed: **"both sides failed"**, and its result is
**"no result recorded"** (/docs). Not a draw, not a loss — no result at all.

### `unterminated` — **NOT DOCUMENTED ANYWHERE. Still email them.**

I searched for the string `unterminated`, case-insensitively, across:

- the rendered `/docs` HTML
- the raw `/docs/agent-contract.md`
- the raw `/docs/rules.md`
- `/terms`, `/privacy`, `/archive`, the home page (including its FAQ), `/leaderboard`
- the starter repo README

**Zero hits.** There is no changelog page, no glossary, no dashboard docs, and no FAQ entry that
mentions it. Web search for `aichessathon "unterminated"` returns nothing about this competition.

**Conclusion: `unterminated` is genuinely undefined by the published rules. The plan to email
hello@aichessathon.com is still necessary and should go out today.**

What I *can* offer is a strong, external, non-authoritative reading — flagged as inference, not
documentation:

`unterminated` is a value from the **PGN standard's `Termination` tag**, whose permitted values
are `abandoned`, `adjudication`, `death`, `emergency`, `normal`, `rules infraction`, `time forfeit`
and `unterminated`, where `unterminated` is specified to mean **"game not terminated"**
(PGN Specification and Implementation Guide, §9.8.1;
http://www.saremba.de/chessgml/standards/pgn/pgn-complete.htm). It pairs naturally with
`Result "*"`, the PGN result for a game with no decision. So the platform is almost certainly
emitting a standards-conformant PGN for a game its referee stopped without reaching a decision —
which is what `Result "*"` plus `Termination "unterminated"` means and nothing more.

Two things follow that the team should carry into the email:

1. **`void` and `unterminated` are not obviously the same thing.** The docs' `void` is
   "both sides failed" and records no result. The team's eight games record `Result "*"` but the
   log *also* says **"Drawn by unterminated"** — the word "Drawn" is doing work there, and the
   docs' `void` row does not say "drawn". Ask which of the two the ladder actually applied.
2. **Our side did not fail in any of the eight**, per `runs/2026-09-08-voids/FINDINGS.md`:
   init 0.4–0.5 s of 90 s, never flagged, 6.0–67.3 s left, nothing on stderr, no `illegal`,
   `crash`, `flag` or `init`. If `unterminated` were `void` under a different label, the docs'
   definition ("both sides failed") does not fit the evidence. That is the sharpest question to
   put to the organisers.

Also worth putting in the email: durations were 170.5–369.6 s and plies 60–282, so it is neither a
fixed wall-clock cap nor the 600-ply `ply_cap`.

### Effect on rating and on W-D-L

The docs are thin here and I will not fill the gap.

- **Documented:** `void` records **"no result recorded"** (/docs failure table). The ladder is
  "a standard rating fitted to your current build's results" (/docs/rules.md, `Ranking`; /docs,
  `Ladder`). A game with no result recorded is not a result, so on the plain reading it is not
  fitted into the rating and does not enter W-D-L. The leaderboard's own columns are
  `Rank | Bot | University | Rating | Games | W-D-L`.
- **Not documented:** whether a void counts toward the `Games` column; the rating system by name
  (Elo, Glicko, something else — the word used is only "a standard rating", though the home page's
  `04 · Criteria` block says "Ranking is by Elo"); the K-factor or equivalent; and, obviously,
  anything at all about `unterminated`.
- **Documented and relevant to scale:** "house bots and house engines play the ladder. The engines
  keep a fixed rating, which holds the scale. None can qualify" (/docs/rules.md).
- **Documented and important:** the rating is fitted to your **current build's** results, and
  **"The ladder only seeds the final Swiss"** — it does not itself decide qualification.

---

## 4. The schedule, exactly

All rows verbatim from https://aichessathon.com/docs/rules.md ("Event constants") unless marked.

| Event | Verbatim |
|---|---|
| Registration | "open now, closes Sep 11 11:00" |
| Qualifier ladder | "4-11 September" |
| Rated rounds | "**every hour, 08:00-22:00** from Sep 4 08:00" |
| Upload close | "Sep 11 11:00" |
| Team changes close | "Creating, joining and leaving a team close Sep 11 11:00" |
| Final qualification | "**13-round Swiss** over locked builds, **Sep 11 afternoon**" |
| Finalist invites | "Sep 11, once the final Swiss has run. Seats are confirmed by reply, first come" |
| Finalists | "the final Swiss decides the London field. **The room holds 50.** Seats fill in seed order, **one per UK member of a team and at most 2 per team**. Invites are issued in that order and confirmed by reply, first come, until the room is full. **Live final Sep 12 at Encode Club, London**" |
| Daily Five | "6-10 September. One attempt a day, five positions, 20 minutes. … Start by **23:40 London**" |

Corroborating from /terms:

> It begins with an online qualification phase from **4–11 September 2026**. Selected participants will be invited to an in-person final at **Encode Club, London** on **12 September 2026**.

And from /docs/agent-contract.md, "Versions":

> The latest submission that passed validation plays each round. **Uploads close Sep 11 11:00.** Your last valid build then freezes, and for eligible teams it alone plays the final qualification Swiss, **which does not open until every submission has finished validating.** Ten uploads per team per day.

**Verdict on `HANDOFF.md`:** "Uploads and rosters lock 11 September 11:00" — confirmed, both of
them, same instant. "13-round Swiss deciding 50 London seats" — confirmed. "Final 12 September" —
confirmed, Encode Club London. "Rated rounds 08:00–22:00" — hours confirmed, and they run
**hourly**, from Sep 4 08:00.

### Time zones — read this carefully

**The only page on the entire site that names a time zone is the Daily Five row: "Start by 23:40
London."** Nothing states a zone for the 11:00 upload close, for the roster close, or for the
08:00–22:00 rated rounds. The organisers are UK-based, the final is in London, the site's edge
region is `lhr1`, and the one explicit zone on the site is London — so London (BST, UTC+1 on
11 September) is the overwhelmingly likely reading, and it is what `HANDOFF.md` assumes. But it is
**an inference, not documentation**.

**Practical instruction: treat the deadline as 11 September 11:00 *in whichever zone is earliest*
and be finished well before it.** With ~46 hours left and two days of uploads, do not spend one of
them discovering the zone empirically. If precision matters, the email to
hello@aichessathon.com should ask.

Also note the sequencing risk: the Swiss "does not open until every submission has finished
validating." A build uploaded at 10:55 that is still validating is a build that may not be your
frozen one. **Upload the final build with hours of margin, and confirm it reaches ACTIVE.**

---

## 5. Eligibility and rosters — the highest-priority item

### The controlling sentences, verbatim

From **https://aichessathon.com/terms**, section "1. Competition format" (page version
`2026-08-31.v3`, fetched 9 September 2026):

> Teams are limited to three members.

> Registration and the online qualification are open worldwide. **A team enters the final qualification stage if at least one member is a UK university student, and only its UK members may take a seat at the in-person final.** Teams are verified before invites are confirmed. Seats are limited and confirmed in the order replies are received. Participants must provide accurate registration information. An invitation to the final is personal to the selected participant or team and may not be transferred without organiser approval.

From **https://aichessathon.com/docs/rules.md**, row `Eligibility`:

> Open worldwide. A team enters the final qualification Swiss if at least one member is a UK university student. Only its UK members can take a London seat, verified before invites

From **https://aichessathon.com/docs**, `Clocks and scoring` table, row `Eligibility`:

> the ladder is open worldwide. A team enters the final Swiss if at least one member is a UK university student, and only its UK members can take a London seat, verified before invites

From **https://aichessathon.com/docs/rules.md**, row `Teams`:

> 1-3 people, one team per person. Creating, joining and leaving a team close Sep 11 11:00

From **https://aichessathon.com/docs/rules.md**, row `Finalists`:

> the final Swiss decides the London field. The room holds 50. Seats fill in seed order, one per UK member of a team and at most 2 per team. Invites are issued in that order and confirmed by reply, first come, until the room is full. Live final Sep 12 at Encode Club, London

From the home page FAQ, question 01 "Who can register?":

> Anyone, anywhere, through the site form. The qualifier is open worldwide. A team enters the final qualification Swiss if at least one member is a UK university student, and only its UK members can take a London seat. Teams are verified before invites go out.

From the home page FAQ, question 04 "Can I enter with a team?":

> Yes, up to three people. Register yourself, then create a team or join one with a teammate's invite link. Playing solo is fine too.

### What this answers, and what it does not

**What qualifies a team for the final:** exactly one condition — **at least one member is a UK
university student**. There is no rating floor, no separate application. The team's belief is
correct. Danny, a Computer Science with AI student at the University of Liverpool, satisfies it on
the plain reading of the words: he is a student at a UK university.

**Danny's seat at the final:** "only its UK members may take a seat at the in-person final", and
seats go "one per UK member of a team and at most 2 per team". With one UK member, the team gets
**one seat**, and it is Danny's. A second seat would require a second UK member.

**What counts as a "UK university student":** **not documented.** The phrase is used four times
across four pages and is never defined. Specifically undefined:
- whether it means enrolled at an institution located in the UK, or a UK national studying anywhere
- whether postgraduate, part-time, foundation-year or recently-graduated students count
- whether a term-time enrolment date matters
The Daily Five wildcard row (/docs/rules.md) is the only place that adds any qualifier at all:
"Eligible means a UK university student who is not an organiser and not on a disqualified team."
That excludes organisers and disqualified teams; it does not define the core term.

**What proof is required:** **not documented.** Three pages say only "verified before invites" /
"Teams are verified before invites are confirmed", and none says what evidence is accepted. The
prize clause of /terms is the only place documentation is mentioned at all:

> Payment is made after the final to bank details the team provides, and the organisers may require proof of identity and of eligibility before paying.

So proof is required **at latest** before payment, and there is a verification step before invites
whose evidentiary standard is unstated. Sensible preparation, not a documented requirement: have a
university email address on the account, a student ID, and an enrolment letter to hand.

**How and by when a roster is changed:** **"Creating, joining and leaving a team close Sep 11
11:00"** (/docs/rules.md; identically on /docs: "Creating, joining and leaving a team close
11 September 11:00"). The *mechanism* is documented only in the home FAQ: "Register yourself, then
create a team or join one with a teammate's invite link." **A prospective member must register on
the site in their own right first, then join via an invite link.** No admin-side roster edit is
documented. Also: **"one team per person"** — Danny cannot be on two teams.

**Team size:** **1 to 3 people.** "Teams are limited to three members" (/terms); "1-3 people"
(/docs/rules.md); "up to three people … Playing solo is fine too" (home FAQ).

### The action, plainly

The dashboard shows the team as **"Ladder only"**, which means no UK university student is
currently on the roster. **The fix is for Danny to be registered and joined to the team before
11 September 11:00.** That is one registration and one invite-link acceptance, it is the single
thing standing between this team and the 13-round Swiss, and the window closes in under 46 hours.
Nothing in the engine work matters if this does not happen.

### Second route to a London seat: the Daily Five

Independent of the Swiss, from /docs/rules.md:

> **Daily Five wildcards** — the top 3 eligible participants each day earn a Finals Day Wildcard, a seat at the London final and **not a place in the bracket**. One per person across the five days, so places roll down. Eligible means a UK university student who is not an organiser and not on a disqualified team

> **Daily Five** — 6-10 September. One attempt a day, five positions, 20 minutes. One wrong move ends a position. Your five are drawn for you. Start by 23:40 London. Anyone signed in may play

> **Daily Five ranking** — positions solved, then the time of your last solve, then who finished first. A position withdrawn as broken counts as solved and adds no time

> **Daily Five fair play** — no engines, no other people, no other accounts, no looking positions up. Every move is timed. Invitations follow review and may include solving a position in person at the final

The Daily Five runs **6–10 September**, so **9 and 10 September are the last two days**. A wildcard
is a seat at the final but not a place in the bracket. Danny is eligible. It is free and it costs
20 minutes. /terms reinforces the fair-play rule:

> The Daily Five is solved alone, on your own account, without an engine, another person or a second account, and an invitation earned from it is personal.

---

## 6. What may be shipped, and what is banned

### The engine ban, verbatim

/docs/rules.md, row `Engines`:

> third party engines are prohibited. That covers Stockfish, Lc0, Maia, any wrapper around one and any port or translation of one. Your moves come from code you wrote. Use any AI support you like to write it, as long as the submission keeps to these rules and you can explain it when asked. **An engine you wrote yourself before the event is your own code.** A model is not required and a classical search is a full entry

### Models, verbatim

/docs/rules.md, row `Models`:

> any network you ship is one you trained yourself. Training it on positions an existing engine labelled is allowed. **Starting from a published chess network is not, so fine-tuning or re-exporting one counts as shipping it.**

/docs/agent-contract.md: "Any network you ship is one you trained yourself, and starting from a
published chess network counts as shipping it."

### Training data vs shipped data — the sentence that decides the opening-book question

/docs/rules.md, row `Training data`:

> unrestricted, including positions annotated by an existing engine. **What ships inside the zip is what the ban covers. A database of another engine's moves or evaluations shipped for lookup at runtime is an engine, not training data.**

### Books and tablebases, verbatim

/docs/rules.md, row `Books and tablebases`:

> opening books and endgame tablebases are permitted as shipped data within the 50 MB cap. `chess.polyglot` and `chess.syzygy` are in the base image

/docs says the same: "Opening books and endgame tablebases are permitted as shipped data, and
chess.polyglot and chess.syzygy are in the base image."

**Reading this for the team's two open items.** These two rows are in tension and the line between
them is the whole question:

- **Syzygy tablebases: unambiguously fine.** They are named as permitted shipped data, `chess.syzygy`
  is in the base image, and they are not any engine's moves or evaluations — they are the solved
  ground truth of the position. Shipping more of the 5-man WDL set, within the 50 MB cap, is
  squarely inside the rules. The only cost is size and probe time.
- **Opening books: permitted in the abstract, but *provenance decides it*.** "opening books … are
  permitted as shipped data" and "a database of another engine's moves or evaluations shipped for
  lookup at runtime is an engine" are both true at once. A Polyglot book compiled from **human
  master game statistics** is a book. A Polyglot book whose move choices are **an engine's
  preferred moves or its evaluations** is, by the letter of the `Training data` row, "an engine,
  not training data" — even though it is called a book. Many well-known public `.bin` books are
  engine-generated or engine-filtered. **Ship a book only if you can state where every entry came
  from**, because /docs/rules.md row `Verification` says each finalist team "walks through how its
  agent was built" and "Disqualification can be retroactive."
- If a book's provenance cannot be established with confidence, the safe construction is to
  generate it yourself from game results, or — noting "Training data … unrestricted, including
  positions annotated by an existing engine" — to use engine annotations as *training* signal for a
  network you train, which is explicitly allowed, rather than as a runtime lookup table, which is
  explicitly not. **This distinction is worth putting in the same email to the organisers**, since
  it is the difference between +Elo and retroactive disqualification.

### Code, obfuscation, native binaries, verbatim

/docs/rules.md, row `Code`:

> what you ship must be source a judge can read. Everything that runs is python from your zip plus the preinstalled stack. **Obfuscated agents are disqualified**

/docs/agent-contract.md:

> Native binaries inside the zip are rejected. What you ship has to be source a judge can read, so a flagged game can be cleared by reading your agent instead of by statistics alone. **Model weights are not binaries, so `.onnx`, `.safetensors` and `.pt` are fine.** File modes inside the zip are ignored and every file is readable by your process. Your zip is first on `sys.path`, so a file named after a module you import, like `chess.py` or `types.py`, shadows the real one.

> Compiled speed comes from the stack, not from your zip. numba JIT compiles your Python in process, and each jitted function pays that compile cost the first time it runs. **Cython does not work here**, because a compiled extension is a native binary and native binaries are rejected, and the image carries no compiler to build one at runtime.

### How compliance is checked, and the penalty

/docs/rules.md, row `Verification`:

> every submission faces automated and human checks. **Each finalist team walks through how its agent was built, and a team that ships a network shows how it was trained. Disqualification can be retroactive.**

/terms §2 and §3:

> Participants must build and operate their own chess agent within the published interface, compute, network, and time limits. … Participants must disclose components and assistance when the specification requires it.

> Agents must produce legal moves, operate reliably, and must not attempt to access another participant's system, hidden match data, organiser infrastructure, or credentials.

> No participant may manipulate pairings, coordinate match outcomes, impersonate another entrant, exploit infrastructure outside the intended game interface, or misrepresent authorship or eligibility. … Suspected vulnerabilities should be reported privately to hello@aichessathon.com and not used for advantage.

> Organisers may pause a match, request logs or a reproducible build, rerun a match affected by a verified technical problem, or **disqualify a submission for a material breach**. Decisions will be based on the published rules, available evidence, and consistent treatment of participants. **An appeal process will accompany the final technical rules.**

/terms §6: "A team disqualified under these rules forfeits any prize, and the organisers may award
it to the next placed team."

**Note on the NNUE plan:** training on positions labelled locally by Stockfish is **explicitly
allowed** ("Training it on positions an existing engine labelled is allowed"). But a team that
ships a network **"shows how it was trained"** at the final. Keep the training pipeline, the data
provenance and the run logs reproducible and presentable. Also confirm Stockfish binaries stay
gitignored and never enter the zip.

---

## 7. Everything else that could change a decision

### Validation and what happens to a failed upload

/docs, `Submissions`:

> **Validation** — build, then two smoke games at the match clock, one as each colour. The verbatim log appears on your dashboard
>
> **Which plays** — your latest submission that passed validation

/docs/agent-contract.md:

> Validation plays two smoke games against a house agent, one as each colour, and publishes the verbatim log. Both games start from curated opening positions.

> The latest submission that passed validation plays each round.

**A failed upload does not replace your live build.** "Your latest submission that **passed
validation**" plays, so a build that fails validation leaves the previous passing build on the
ladder. That is a genuine safety net — but it burns one of the ten daily uploads. `HANDOFF.md`
records the observed dashboard states as BUILDING → SMOKE TEST → ACTIVE.

The smoke games use **the real match clock** and **curated opening positions**, not the standard
start — so a smoke pass is a meaningful signal about the real environment.

### Diagnostics you can actually read (and `CLAUDE.md` says you cannot)

/docs/agent-contract.md:

> Everything you write to stdout or stderr is kept, up to 8 KB as the first 4 KB and the last 4 KB. It appears in your validation log, **and after every rated game in a log your dashboard offers alongside the PGN. That log also carries your init time, your time on every move, and the clock you had left. Only your own team can read it.**

Per-move timings and remaining clock for **every rated game**, plus up to 8 KB of your own stderr,
are available on the dashboard. `CLAUDE.md`'s claim that output is "discarded in rated games" is
wrong, and this is free instrumentation the team is under-using. The 4 KB-head/4 KB-tail split
means a chatty agent loses the middle — log sparsely and log the end.

### Pondering — you cannot

/docs/agent-contract.md:

> **Your process is suspended while your opponent moves**, so work you leave running between your own moves does not run and each side has the core to itself while it thinks.

/docs/rules.md, row `Pondering`, says the same. **There is no pondering.** Do not build for it.
This directly contradicts `CLAUDE.md`.

### Concurrency

/docs/agent-contract.md:

> Games are independent, so **two of your games can run at the same time in separate containers**. Your agent is never asked for two moves at once.

`CLAUDE.md` has this right. Note "in separate containers" — no shared state between them, and each
gets its own core, so concurrency does not halve your speed.

### Repetition — the referee claims for you

/docs/agent-contract.md:

> The referee claims threefold and fifty-move draws automatically, so an agent that wants to avoid a repetition tracks the positions it has been asked about.

This matters given the void-games pattern in `runs/2026-09-08-voids/FINDINGS.md` (seven of eight
final positions had already occurred twice with a repeating move available). The referee claims the
draw the moment the third occurrence appears; the agent must avoid reaching it, and v8 already
tracks this.

### The curated opening positions

/docs/agent-contract.md:

> The first fen you receive is the starting position of the game. **Games start from curated opening positions, not always the standard start. Every starting position is close to level. The set of positions is not published in advance, though finished games reveal the positions they were played from.** Repetition and fifty-move counts begin there.

/docs/rules.md, row `Openings`:

> every game starts from a curated opening position that is close to level. Knockout ties play each position once with each colour

**The set is not published**, and that is stated explicitly — so no amount of searching will find
it. But **"finished games reveal the positions they were played from"**, and the team has 60+ rated
games' worth of PGNs. **The starting FENs of your own finished games are a legitimate, documented
sample of the position set** — that is the only characterisation available, and it directly informs
whether an opening book is worth building and what it should cover. Note also "Repetition and
fifty-move counts begin there", so the fifty-move counter in the first FEN is not necessarily zero.
The home page names three of its illustrative boards "Opera", "Evergreen", "Century" — famous
games — which hints at, but does not establish, curation from historical games.

### Tie-breaks and the Swiss

/docs, `Clocks and scoring`:

> **Qualification** — a 13-round Swiss over the locked builds decides the order the 50 London seats fill, by points. An odd field gives one team a 1-point bye. Seats go one per UK member and at most two per team
>
> **Tie-breaks** — points, Buchholz, head-to-head, **earlier final submission**. A level knockout tie goes to the better Swiss standing

/docs/rules.md, row `Qualification`: "only the locked-build final Swiss counts, by points."

**"Earlier final submission" is a tie-break.** If two teams are level on points, Buchholz and
head-to-head, the team that uploaded its final build **earlier** wins the tie. That is a small,
free, real argument for locking the final build well before 11:00 on 11 September rather than at
the wire — on top of the validation-queue risk.

### How the ladder rating works

/docs/rules.md, row `Ranking`:

> a standard rating fitted to your current build's results. **The ladder only seeds the final Swiss**

/docs, `Ladder`:

> rated rounds every hour, 08:00 to 22:00, ranked by a standard rating fitted to your current build's results. The ladder only seeds the final Swiss

/docs/rules.md, row `House bots`:

> house bots and house engines play the ladder. The engines keep a fixed rating, which holds the scale. None can qualify

The leaderboard page describes itself as "Ratings across the rated rounds of the online qualifier.
The ladder only seeds the final Swiss", with columns `Rank | Bot | University | Rating | Games |
W-D-L` and stage tabs `Live`, `Qualifier ladder`, `Final qualification`, `London final`. The home
page's criteria block says "Ranking is by Elo". **The exact rating algorithm and its parameters are
not documented.** Two things are documented and matter:

1. The rating is fitted to your **current build's** results — a new upload is evaluated on its own
   results, which explains why `HANDOFF.md` observes v10's rating "has not yet moved."
2. **The ladder does not qualify anyone.** Only the 13-round Swiss over locked builds does, by
   points. Ladder rating decides seeding, and seeding decides the **order** the 50 seats fill.

### The London final format

/docs/rules.md, row `Prizes`, and /terms §6:

> £1,000 winner, £500 runner-up, £250 third, at the London final. **Third is the losing semi-finalist with the better final Swiss standing.** Awarded to the team, split as the team decides

The mention of semi-finalists, plus the leaderboard's `knockout` stage tab and "Knockout ties play
each position once with each colour" (/docs/rules.md, `Openings`), establishes that **the London
final is a knockout bracket**. The bracket size, the pairing rule and the number of games per match
are **not documented**. /terms §6 adds: "Payment is made after the final to bank details the team
provides, and the organisers may require proof of identity and of eligibility before paying."

### Rules precedence

/terms §7:

> This page is the competition framework. The operational detail lives in the documentation. Material changes will be versioned and communicated to registered participants, who will be asked to acknowledge any change that materially affects participation. **If documents conflict, the latest dated competition rules take precedence for competition matters.**

So `/terms` (currently `2026-08-31.v3`) outranks `/docs` where they conflict. On everything checked
here they agree.

---

## 8. Things that are genuinely not documented

Stated as such rather than guessed:

1. **`unterminated`** — appears nowhere on the site or in the starter repo. §3.
2. **The time zone** for the 11:00 upload/roster close and the 08:00–22:00 rated rounds. Only the
   Daily Five names one ("London"). §4.
3. **What "UK university student" means** — no definition of enrolment, level, nationality or
   institution. §5.
4. **What proof of eligibility is accepted, and when** — only "verified before invites" and, for
   payment, "may require proof of identity and of eligibility". §5.
5. **The rating algorithm and its parameters** — "a standard rating"; the home page says "Elo". §7.
6. **Whether a void or unterminated game counts toward the `Games` column** or affects rating. §3.
7. **Maximum *zipped* size** — only the 50 MB unzipped figure exists anywhere.
8. **The knockout bracket's size, pairings and games per match** at the London final. §7.
9. **The curated opening set** — explicitly stated as not published in advance. §7.
10. **The appeals process** — /terms says one "will accompany the final technical rules"; it has
    not been published.

---

## 9. What to do in the next 46 hours, in priority order

1. **Get Danny registered and onto the roster before 11 September 11:00.** One registration, one
   invite link. Without it the team plays no Swiss, takes no seat and wins nothing, regardless of
   engine strength. Closes with the upload deadline. (§5)
2. **Email hello@aichessathon.com today**, with three questions in one message: (a) what
   `unterminated` is and how those eight games were scored, given our side did not fail; (b) the
   time zone of the 11:00 close; (c) whether an opening book compiled from *human* game statistics
   is a permitted book rather than a prohibited engine database. (§3, §4, §6)
3. **Play the Daily Five on 9 and 10 September.** Last two days. A top-3 finish is an independent
   London seat for Danny. 20 minutes, no engines, alone. (§5)
4. **Fix `CLAUDE.md` / `AGENTS.md`** — the pondering claim and the "stderr discarded in rated
   games" claim are actively misleading, and the 60 s / six-uploads / 300-ply numbers are stale.
   (§1a) *(Not done here: I was instructed not to edit existing files.)*
5. **Raise the harness's `INIT_BUDGET_S` to 90 and `PLY_CAP` to 600 with a draw**, or accept that
   local long-game results misrepresent the endgame. Owner's call. (§1c)
6. **Start pulling per-move timing logs from the dashboard** for rated games — they exist, they are
   free, and `CLAUDE.md` said they did not. (§7)
7. **Lock the final build early.** Validation must finish before the Swiss opens, and "earlier
   final submission" is a documented Swiss tie-break. (§4, §7)
