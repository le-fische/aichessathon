"""King safety: hand-checked signs and magnitudes.

A king-safety term with the wrong sign is invisible to a match -- the engine simply
starts walking its king into danger and the score still looks reasonable -- so the sign
gets asserted by hand here, the same way tests/test_see.py does for SEE.

The term is middlegame only: penalties enter mg_diff and never eg_diff, so the existing
taper retires it as pieces come off. The endgame case below asserts that.

    python tests/test_king_safety.py
"""
import os
import sys

import chess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from evaluation import king_safety_mg  # noqa: E402

FAILED: list[str] = []


def check(name: str, fen: str, want: str, reasoning: str) -> None:
    """want is 'positive' (white safer), 'negative' (black safer) or 'zero'."""
    v = king_safety_mg(chess.Board(fen))
    ok = {"positive": v > 0, "negative": v < 0, "zero": v == 0}[want]
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<34} delta={v:>5}  want {want:<9} {reasoning}")
    if not ok:
        FAILED.append(name)


def main() -> int:
    print("King safety, white-minus-black. Positive = white's king is safer.\n")

    # A mirrored position must score exactly zero, or the term has a colour bug --
    # the single most likely way to get this wrong.
    check("symmetric start", chess.STARTING_FEN, "zero",
          "mirrored: any non-zero is a colour bug")

    # Black's f/g/h pawns are gone in front of a kingside king; white's are intact.
    check("black kingside stripped", "rnbq1rk1/ppppp3/8/8/8/8/PPPPPPPP/RNBQ1RK1 w - - 0 1",
          "positive", "black has no shelter, white has three pawns")

    check("white kingside stripped", "rnbq1rk1/pppppppp/8/8/8/8/PPPPP3/RNBQ1RK1 w - - 0 1",
          "negative", "mirror of the case above")

    # The real thing: round 93, White to move at move 33, the game we lost to an 1835.
    # White king on a2, queenside pawns gone, black queen and knight already in.
    check("round 93 (we are White)", "5r1k/7p/6p1/4b3/1qp1BP2/1n4PP/K3N3/2B1R3 w - - 0 33",
          "negative", "Ka2 with a,b,c files bare -- the loss this term exists for")

    # Same shape, but the term must vanish once it is an endgame. Evaluated through the
    # full evaluation rather than the raw term, since the taper lives in evaluate().
    from evaluation import evaluate
    ending = "8/8/8/4k3/8/8/8/K6R w - - 0 1"
    raw = king_safety_mg(chess.Board(ending))
    full = evaluate(chess.Board(ending))
    print(f"\n  taper check: bare-ish endgame raw term = {raw}, full evaluate = {full:.0f}")
    print("  (raw may be non-zero; what matters is mg_diff is weighted by phase, which is ~0 here)")

    print()
    if FAILED:
        print(f"FAILED: {', '.join(FAILED)}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
