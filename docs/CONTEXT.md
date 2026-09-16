# Session handoff — read this first

Written 9 September 06:24 UTC. Roughly 52 hours to the lock (11 September 11:00).
`HANDOFF.md` has the engineering detail; this file is the context a fresh session needs.

## Role
Le has more Antigravity (Gemini) credits than Claude credits. Claude plans, prompts,
reviews and verifies; Antigravity builds. Be economical: read the repo with device_bash
rather than long chat transcripts, one consolidated command over five small ones.
Verify every claim against disk -- three chats have reported work that was on no branch,
and one reported a node rate 3.7x the truth.

## State
v10 live (zip sha 5eae2f15, ACTIVE since 8 Sept 07:26). Rating 1693, peak 1729,
rank #155 of 410. Record 25-17-25, the 8 Voids are all pre-v10. Branch `nnue`.
Roster SECURED: the panel reads "Enters the final qualification Swiss" -- Gede Danny
Putra Budiada is the UK student. Only UK members may take a London seat, so Danny attends.
v10 is worth about +170 Elo over v9, almost entirely from compiling the search with numba.

## Decisions already made
- **NNUE is KILLED.** 768x256 on 2M Stockfish-labelled positions scored 1 point in 98
  games across two gates (0/60, then 1.0/43 = 2.3%). Speed was never the problem and the
  accumulator equivalence test genuinely passed; the network never learned a usable
  evaluation. Do not revive it.
- **The 28s init is overhead, not sophistication.** It is numba compiling at startup. The
  budgets with real room are the 48 MB of unused zip and the ~9% of node cost the
  evaluation uses.
- Horizon fixes 50.8% +/- 5.1% and bishop pair 50.0% +/- 6.5% -- both unmeasured, both
  shipped in v10, both kept.

## Open work, ranked
1. **SEE (static exchange evaluation)** -- biggest missing piece, nobody on it. Ordering
   is MVV-LVA only and cannot tell a winning capture from a losing one. Skip SEE<0
   captures in quiescence, order the rest by SEE. Typically +20 to +50 Elo.
2. **Gate Terms 3 and 4** (e078c41 rook on open file, 5963d9c doubled/isolated pawns).
   Committed, unmeasured, NOT in v10. They need numbers before v11.
3. **Opening book** -- Danny, own branch, see TASKS.md. We ship none.
4. **The flag question** -- ~8 games lost on time across ~160 local games, ZERO on the
   ladder. Probably CPU contention from two engines on one Mac. The clock has never been
   tested past move 70; tools/clocktraj.py is the instrument.
5. v11 upload once anything above is gated.

## Note on tooling
Computer-use access to Antigravity is currently blocked for Le -- the approve control is
the "All" chip on the right of the app row, not a button labelled "Allow", and it appears
unclickable for him. Until that is resolved, hand him prompts to paste rather than driving
the app directly.
