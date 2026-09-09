# The Illegal game was a game we won, and the numba move generator is clean

Worked on `danny-test`, 2026-09-09. Follows `runs/2026-09-08-voids/FINDINGS.md`,
which left two things open: the Illegal game had never been seen, and the numba
path had never been probed. Both are closed here.

Reproduce with `tools/perft_deep.py`, `tools/movegen_audit.py` and
`tools/probe_agent.py`. Raw output in this directory:
`perft_deep.txt`, `movegen_audit.txt`, `probe_numba_agent.{stdout,stderr,json}`,
`probe_nsearch_direct.txt`.

## Headline

**There is no move-generation or protocol bug in the numba path, and round 32 —
the one game recorded `Illegal` — is a game we WON because the opponent played
the illegal move.** The "might be nine games free" premise that motivated this
task is dead. Nothing here is recoverable rating.

## 1. Round 32 is a win, not a loss

`aichessathon-round-32-0x88.log` appeared in the log folder on 8 Sept at 23:56,
after the previous write-up was finished at 18:06. It reads:

    Colour         Black
    Opponent       0x88
    Won by illegal
    Left at end    61.5 s
    Ready in       0.5 s     (of 90 s budget, 1 percent)
    OUTPUT         Nothing written to stderr

The PGN is `[White "0x88"] [Black "lefischer"] [Result "0-1"]
[Termination "illegal"]`. agent-contract.md, fetched 9 Sept: *"An illegal
move... loses that game."* White made it, White lost. All 20 of our moves were
legal, slowest 4.9 s on move 1.

## 2. What the 17-15-20 record over 60 rounds actually means

The docs do not say how `void` or `unterminated` are scored. `rules.md` gives
only *"Both sides failing voids the game"*; `unterminated` appears nowhere in
either document.

The arithmetic settles it: **17 + 15 + 20 = 52, and 60 - 52 = 8, exactly the
void count.** The 8 void games are excluded from the win/draw/loss record. They
are not draws and not losses. **Their direct rating cost was zero.** What they
cost is 13 percent of the sample.

This contradicts the log wording, which says "Drawn by unterminated". The
arithmetic is the harder evidence. Both belong in the email to the organisers.

## 3. None of this evidence describes the live build

All 9 logged games finished 4-6 September. **v10 went live 8 September.** Every
conclusion drawn from these logs describes v9 or earlier. That also explains
"Nothing written to stderr" in all of them: the unconditional import print
landed in commit `0d2d188` on 7 September, after these games were played. The
"free integrity check" proposed in `DANNY-LANE.md` section 7 is valid from v10
onward and proves nothing about these logs.

## 4. Perft: 121 depths compared, 121 match, 0 mismatch

`tests/test_perft.py` does compare `bitboard.divide` against python-chess, but
only over 8 positions to depth 4-5. It has no standard position 4, 5 or 6, and
no en-passant, castling or promotion edge cases. `tools/perft_deep.py` closes
that gap with 24 positions.

    121 depths compared: 121 MATCH, 0 MISMATCH, 11 skipped (>3M nodes)
    PASS: every depth compared against python-chess matched exactly

Positions: startpos, Kiwipete, standard 3 / 4 / 4-mirrored / 5 / 6,
ep-horizontal-pin, ep-pinned-by-bishop, ep-rook-pin-on-file,
ep-capture-gives-check, castle-short-gives-check, castle-long-gives-check,
castle-prevented, castle-through-attacked, promote-out-of-check,
underpromote-to-check, self-stalemate, discovered-check, and two
stalemate/checkmate positions.

The 11 cells too large to cross-check against python-chess in reasonable time
were compared against the published reference counts instead, and independently
reproduce all of them: 119,060,324 / 193,690,690 / 11,030,083 / 15,833,292 /
89,941,194 / 164,075,551 / 3,821,001. Node rate 14-21 M/s on this Mac.

## 5. Encoding audit: castling and promotion are correct

`tools/probe_agent.py` only inspects the one move the search chooses, so it can
miss a bad move that the search happened not to pick. `tools/movegen_audit.py`
decodes the whole of `divide(..., 1)` and diffs the full move set against
python-chess, over the 32 suite positions plus 16 positions constructed to force
castling and promotion.

    48 positions, 0 with a move-generation or encoding fault
    castling moves generated and encoded: 19
    promotion moves generated and encoded: 64
    en-passant captures present in these positions: 6

**`DANNY-LANE.md` section 9's "the castling encoder is still unverified" is now
closed.** Castling encodes king-from/king-to (`e1g1`, `e1c1`, `e8g8`, `e8c8`),
never the Shredder form `e1h1`/`e1a1` — `decode_move` ignores the castle flag
and writes from/to, which is the correct behaviour for this protocol. Black-side
castling verified. Under-promotion verified for both colours and both capture
diagonals (12 promotion moves = 3 target squares x 4 pieces). Rights are
respected, transit squares are checked, and castling out of check is refused.

## 6. The adversarial suite against the numba path

Previously the suite had only ever run against the pure-Python fallback. Run
through `agent.py` with `CHESSATHON_REQUIRE_NUMBA=1`:

    32 cases, 2 that would lose a rated game, 0 soft failures

Both failures are the two positions with zero legal moves
(`stalemate_no_legal_moves`, `checkmate_delivered`), where `agent.py` returns
the literal string `"e2e4"`. That defect was already known and reported.

`agent.py` silently substitutes a legal move when nsearch returns a bad one, so
a fault could be masked. Two checks against that:

- stderr from the run contains exactly 4 tracebacks, all `StopIteration` from
  those same 2 terminal positions. Nothing else was caught and hidden.
- `tools/scratch/probe_nsearch.py` calls `nsearch.get_move` directly, bypassing
  the substitution:

      32 cases, 0 faults, 2 raises in positions with zero legal moves

No clock overshoot anywhere. The panic cases returned in 0.1 to 1.4 ms with 300,
1 and 0 ms left on the clock.

## 7. Defects to report

Files owned by the numba chat; reported, not patched.

1. `nsearch.py:528` — the `best_move == 0` branch does
   `return next(iter(board.legal_moves)).uci(), ...`, which raises
   `StopIteration` in a terminal position. `agent.py:133` then returns the
   literal `"e2e4"`, a fabricated illegal move sitting in the crash handler.
   Both should return `"0000"`. Theoretical: the runner should never ask.
2. Not a defect, recorded so nobody chases it: the search never *voluntarily*
   castles in the contrived rook-and-king suite positions, preferring `a1a8` /
   `a1a7`. Section 5 proves the castles are generated and correctly encoded in
   those same positions, so this is search preference, not an encoder fault.

## 8. Not answerable with the data on hand

Quantifying how many of the 60 rated rounds show the shuffling shape needs the
PGNs. Only 10 exist locally. Of those, all 8 voids have quiet tails of 8 to 67
plies and the 2 decisive games have tails of 7 and 1 — the same finding as the
8 Sept write-up, at n = 10. **Pulling the other ~50 PGNs off the dashboard is
the prerequisite.**

## Next

1. Stop hunting an automatic-loss bug in `nsearch` / `bitboard`. It is not there.
2. The one live engine defect is unchanged: the engine cannot convert won
   endgames. `_mate_drive` is gated on `game_phase <= 6` AND one side having
   nothing but a king, so rook endings with material on both sides get no
   progress gradient. Rounds 6, 7 and 31 are the test set.
3. Cheap and worth doing: merge `tools/perft_deep.py`'s position list into
   `tests/test_perft.py` so the gate covers it.
4. Email the organisers: `unterminated` is undocumented, the logs call it
   "Drawn" but the record arithmetic excludes those games entirely.
