# What our rated losses actually look like, across 23 games

Pure log analysis, no engine time. Sources: `v10-game-logs`, `v11-game-logs`,
`voided-game-logs`, deduplicated by round number.

## Every single loss is a checkmate

    r80  Black  74mv  left  9.3s  Scotch Game      Lost by checkmate
    r83  Black  37mv  left 28.5s  French Advance   Lost by checkmate
    r90  White  52mv  left  2.5s  Sicilian Closed  Lost by checkmate
    r93  White  32mv  left 42.4s  Sicilian Closed  Lost by checkmate

Four losses in 23 games, **all four by checkmate**. Not one on time, by adjudication or
by resignation. Whatever is costing us games, it is not the clock and not a protocol
fault -- both of which were the leading theories going into today.

Two of the four ended with **28.5 s and 42.4 s still on the clock**. We are being mated
with a third of our time unspent.

## By colour and by length

    White   +4 =6 -2   58.3%   (n=12)
    Black   +5 =4 -2   63.6%   (n=11)

    short  <40 mv   +2 =3 -2   50.0%   (n=7)
    medium 40-70    +6 =3 -1   75.0%   (n=10)
    long   >70 mv   +1 =4 -1   50.0%   (n=6)

Colour balance is fine. **Short games are the weak band** -- 50% under 40 moves against
75% in the 40-70 range -- and two of the four losses are short games we lost quickly
while holding a large clock surplus. That is the signature of getting mated in the
middlegame, not of grinding out a worse position.

## The mechanism, and why it is not one bad opening

Both White losses are the Sicilian Closed, which looks like an opening problem until you
look at the king:

    r90  1. O-O  (kingside)   ... later Kf1, Kf2, Kg2, Kf2
    r93  5. O-O-O (queenside) ... later Kb2, Ka2, Kb1, Ka1

Opposite castling, same shape: the king shuffling under pressure in the late middlegame.

That is exactly what an evaluation with **no king-safety term** produces. Until v12 the
only signal for king placement was the PeSTO middlegame king table, which rewards
castled and corner squares and says nothing about whether the pawns in front of the king
are still there or whether a file has opened onto it. The engine had no reason to keep
cover and no way to see an attack forming.

So king safety is motivated by both losses independently, not just by round 93. The two
halves added in `b5462c9` and `9d21403` address exactly this: shelter and open files for
"is the cover intact", attacker count for "how much is aimed at it".

## What this rules out

- **Not the clock.** Losses came with 2.5-42.4 s left and, in v11, zero moves over
  budget. The quiescence fix already removed the one real clock defect.
- **Not move generation.** 121 perft depths against python-chess, 0 mismatches.
- **Not endgame conversion**, at least not in these games -- all four losses were decided
  in the middlegame, and the one conversion failure we did find (KBNvK) is now fixed by
  the root DTZ probe.

The remaining gap in these games is middlegame king safety, which is where v12 spent its
effort.
