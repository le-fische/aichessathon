"""Static exchange evaluation: positions where the answer is known by hand.

A SEE sign error is invisible to game-based testing -- the engine just quietly stops
considering a good capture, and a 5-game smoke test looks fine. These are the cases that
catch it.

The x-ray case is differential on purpose. Asserting a single value there is useless: a
swap loop that never sees the back rook returns the same 0 as a correct one when the
defenders happen to balance. Two positions differing only by the back rook, with the
enemy king moved off the target square so it does not equalise them, is the test that can
actually fail.

    CHESSATHON_REQUIRE_NUMBA=1 python tests/test_see.py
"""
import os
import sys

import chess
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bitboard import decode_move, from_chess_board  # noqa: E402
from nsearch import generate_pseudo_legal_moves, see  # noqa: E402

FAILED: list[str] = []


def see_of(fen: str, uci: str) -> int:
    """SEE of `uci` in `fen`, via the engine's own move generator and encoding."""
    board = chess.Board(fen)
    pieces, colors, state = from_chess_board(board)
    buf = np.zeros(256, dtype=np.uint32)
    count = generate_pseudo_legal_moves(pieces, colors, state, buf)
    for i in range(count):
        if decode_move(buf[i]) == uci:
            move = buf[i]
            if (move >> 18) & 0x7 == 6:  # NONE
                raise AssertionError(f"{uci} in {fen} is not a capture; the case is vacuous")
            return int(see(pieces, colors, state, move))
    raise AssertionError(f"engine did not generate {uci} in {fen}")


def expect(name: str, fen: str, uci: str, want: int, reasoning: str) -> None:
    got = see_of(fen, uci)
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name:<32} see={got:>6}  want {want:>6}   {reasoning}")
    if not ok:
        FAILED.append(name)


def main() -> int:
    print("SEE, centipawns (P=100 N=320 B=330 R=500 Q=900, king 10000 so it sorts last)\n")

    expect("RxP undefended", "4k3/8/8/8/8/8/7p/4K2R w - - 0 1", "h1h2",
           100, "+100, nothing recaptures")

    expect("QxP defended by pawn", "4k3/8/2p5/1p6/8/3Q4/8/4K3 w - - 0 1", "d3b5",
           -800, "+100 pawn, then cxb5 takes the queen: 100-900")

    expect("RxR defended by rook", "3rk3/3r4/8/8/8/8/8/3RK3 w - - 0 1", "d1d7",
           0, "+500 -500, even trade")

    expect("NxP defended by pawn", "4k3/8/1p6/2p5/8/1N6/8/4K3 w - - 0 1", "b3c5",
           -220, "+100 pawn, then bxc5 takes the knight: 100-320")

    # --- x-ray, differential -------------------------------------------------------
    # Black king on h8, NOT e8: on e8 it defends d7 and both positions come out 0,
    # which would make this pass whether or not the x-ray works.
    print()
    without = see_of("3r3k/3r4/8/8/8/8/3R4/4K3 w - - 0 1", "d2d7")
    with_back = see_of("3r3k/3r4/8/8/8/8/3R4/3RK3 w - - 0 1", "d2d7")
    print(f"  x-ray, one white rook   see={without:>6}  want      0   +500 -500")
    print(f"  x-ray, rook behind rook see={with_back:>6}  want   +500   +500 -500 +500, Rd1 sees through Rd2")
    for label, got, want in (("x-ray without", without, 0), ("x-ray with", with_back, 500)):
        if got != want:
            FAILED.append(label)
            print(f"  FAIL  {label}: got {got}, want {want}")
    if without == with_back:
        FAILED.append("x-ray differential")
        print("  FAIL  x-ray differential: identical with and without the back rook, "
              "so the swap loop is not re-deriving slider attacks against live occupancy")

    print()
    if FAILED:
        print(f"FAILED: {', '.join(FAILED)}")
        print("Do not ship SEE with a sign error: it silently skips good captures.")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
