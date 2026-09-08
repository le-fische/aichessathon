# Round 17: a won king-and-rook endgame drawn by repetition

*Rewritten 09:00 UTC after the original was deleted along with most of `runs/`.
Reproducible from the scripts here.*

Spotted by the user, verified here. **This corrects a conclusion stated twice in
`../2026-09-05-perf/FINDINGS.md`.**

## What happened

Rated 17, White vs `noob`, drawn by threefold repetition. Final position:

    4R3/8/8/3k1K2/8/8/8/8 w - - 15 83

**King and rook against a bare king, a rook up.** K+R vs K is a forced mate. We
drew it. Material trace (`analyse17.py`, `game17.san`): +1 by half-move 60, +3
by 100, **+5 from half-move 136**, drawn at 151.

## What it was not

**Not time.** The match log: 75 moves, 142.0 s used, **15.5 s left at the end**,
0.6-1.1 s per move through the endgame. The `time_left_ms < 3000` panic path
never fired.

**Not depth.** Tracing the engine from that position it reaches **depth 8 to 10**
on every move.

**Not the draw score.** Two repetition fixes were built and tested, and neither
helped:
- filtering repetition-claiming moves at the root — still draws, by a different
  repetition;
- seeding `SearchContext.path_keys` with the whole game history so the search can
  see that returning to an earlier position claims a draw — still draws.

CONTEMPT stays at 0.0.

## What it was

`trace17.py`:

    B Ke5
    W Kg4    depth  8  eval -504  black-king-to-edge 6  king-distance 2
    B Kd5
    W Kf5    depth  9  eval -529  black-king-to-edge 6  king-distance 2
    B Kd4
    W Re8    depth  9  eval -531  black-king-to-edge 6  king-distance 2
    B Kd5
    W Rg8    depth 10  eval -529  black-king-to-edge 6  king-distance 2
    B Kd4
    W Re8    depth 10  eval -531  black-king-to-edge 6  king-distance 2

`Re8`, `Rg8`, `Re8`, `Rg8`. The black king never approaches the edge and the
kings never converge, because **nothing in the evaluation rewards either**. Once
the losing side is down to a bare king the tapered piece-square tables give no
gradient: every shuffle scores within 2 centipawns of every other, so the choice
among them is arbitrary. Mate from a centralised defending king is 30+ plies
away, well past depth 10, so the search cannot see it either.

The engine is not blind to repetition. **It is blind to progress.** Repetition is
what arbitrary shuffling produces.

## The fix

A basic-mate drive in `evaluation.py`, gated on `game_phase <= 6` **and** exactly
one side having nothing but a king, so it cannot perturb a position where both
sides still have material:

    drive = 16.0 * centre_distance(losing_king) + 4.0 * (14 - king_gap)

Mirrored in `bitboard.evaluate` so the numba port stays equivalent.
`evaluation-with-mate-drive.py` here is the patched file as shipped.

`verify_matedrive.py` checks both halves:

**Safety — identical on all 7,663 random positions.** Random legal games, old
evaluation against new, every position reached. Not one differs.
`tests/test_evaluate.py` now carries the same random walk as a permanent gate.

**Conversion:**

| position | before | after |
|---|---|---|
| K+R vs K, centre | threefold repetition | **checkmate** |
| K+R vs K, round 17 | threefold repetition | **checkmate** |
| K+Q vs K, centre | checkmate | checkmate |

K+Q vs K already worked — a queen is strong enough that the tables plus a shallow
search stumble into mate. K+R vs K needed this.

Shipped in platform v6.

## Correcting the record

`../2026-09-05-perf/FINDINGS.md` concluded from round 14 that "draw avoidance is
not the problem, in the tree or at the root". Round 14 supported it: a pawn down
with opposite-coloured bishops, the draw was the best available result. One game
was too small a sample.

What survives: **contempt is not the lever.** Two further repetition fixes were
built and tested here and neither helped. What does not survive: "repetition
draws are fine". The defect that conclusion was hiding is an evaluation that
cannot convert basic mates.

## Still unmined

Four of our games are threefold-repetition draws: rounds 6, 7, 14 and 17. Rounds
6 and 7 have never been examined. `analyse17.py` replays a game from its PGN and
prints the material trace — point it at both.

## Reproduce

```bash
cd runs/2026-09-05-krk
uv run python analyse17.py         # material trace of the game
uv run python trace17.py           # what the engine plays from the won endgame
uv run python verify_matedrive.py  # equivalence on 7,663 positions, plus conversion
```
