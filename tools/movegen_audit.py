"""Exhaustive depth-1 audit of the numba move generator's UCI encoding.

`tools/probe_agent.py` only ever looks at the ONE move the search chose, so it
can pass while the generator emits garbage for every move it did not pick.
This tool decodes EVERY move `bitboard.divide(..., 1)` calls legal and
compares the whole set against python-chess.

That catches, in one pass:
  - missing moves (castling, en passant, under-promotion never generated)
  - extra moves (illegal castles, e.p. through a pin, moves that leave the
    king in check)
  - encoding faults (Shredder-notation castling e1h1, a promotion with no
    suffix, a promotion suffix on a non-promotion)

Positions come from tools/fen_suite.py plus a castling/promotion set that the
suite does not force the search to actually play.

Usage:
    CHESSATHON_REQUIRE_NUMBA=1 python tools/movegen_audit.py
"""

from __future__ import annotations

import os
import sys

import chess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bitboard  # noqa: E402
from fen_suite import all_cases  # noqa: E402

# Positions chosen so that castling and promotion moves MUST appear in the
# generated list, whatever the search would have preferred to play.
EXTRA: list[tuple[str, str]] = [
    ("castle_white_both", "4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1"),
    ("castle_black_both", "r3k2r/8/8/8/8/8/8/4K3 b kq - 0 1"),
    ("castle_black_kingside_only", "r3k2r/8/8/8/8/8/6B1/4K3 b kq - 0 1"),
    ("castle_all_four_rights", "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"),
    ("castle_rook_attacked_is_legal", "4k3/8/8/8/8/8/1b6/R3K2R w KQ - 0 1"),
    ("castle_king_in_check", "4k3/8/8/8/4r3/8/8/R3K2R w KQ - 0 1"),
    ("castle_blocked_b1", "4k3/8/8/8/8/8/8/RN2K2R w KQ - 0 1"),
    ("promo_white_all_four", "4k3/3P4/8/8/8/8/8/4K3 w - - 0 1"),
    ("promo_black_all_four", "4k3/8/8/8/8/8/3p4/4K3 b - - 0 1"),
    ("promo_black_capture_both_ways", "4k3/8/8/8/8/8/3p4/2R1K1R1 b - - 0 1"),
    ("promo_white_capture_both_ways", "2r1k1r1/3P4/8/8/8/8/8/4K3 w - - 0 1"),
    ("promo_under_check_evasion", "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8"),
    ("ep_black_capture", "8/8/8/8/2pP4/8/8/4K2k b - d3 0 1"),
    ("ep_white_capture", "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1"),
    ("ep_two_captures_available", "4k3/8/8/2PpP3/8/8/8/4K3 w - d6 0 1"),
    ("ep_discovered_check_pin", "8/8/8/8/k2Pp2Q/8/8/3K4 b - d3 0 1"),
]


def decoded_moves(fen: str) -> list[str]:
    board = chess.Board(fen)
    pieces, colors, state = bitboard.from_chess_board(board)
    _total, valid, _npm = bitboard.divide(pieces, colors, state, 1)
    return [bitboard.decode_move(int(m)) for m in valid]


def audit_one(tag: str, fen: str) -> tuple[bool, list[str]]:
    board = chess.Board(fen)
    want = sorted(m.uci() for m in board.legal_moves)
    got_list = decoded_moves(fen)
    got = sorted(got_list)

    problems: list[str] = []
    if len(got_list) != len(set(got_list)):
        dupes = sorted({m for m in got_list if got_list.count(m) > 1})
        problems.append(f"duplicate moves emitted: {dupes}")

    missing = sorted(set(want) - set(got))
    extra = sorted(set(got) - set(want))
    if missing:
        problems.append(f"MISSING {len(missing)}: {missing}")
    if extra:
        problems.append(f"EXTRA (illegal or misencoded) {len(extra)}: {extra}")

    return (not problems), problems


def main() -> int:
    print("warming numba...", flush=True)
    print(f"warmup {bitboard.warmup():.2f}s\n", flush=True)

    positions: list[tuple[str, str]] = [(c.id, c.fen) for c in all_cases()]
    positions.extend(EXTRA)

    failures = 0
    castles_seen = 0
    promos_seen = 0
    eps_seen = 0

    for tag, fen in positions:
        ok, problems = audit_one(tag, fen)
        board = chess.Board(fen)
        n = board.legal_moves.count()
        got = decoded_moves(fen)
        castles = [m for m in got if m in ("e1g1", "e1c1", "e8g8", "e8c8")
                   and board.piece_type_at(chess.parse_square(m[:2])) == chess.KING]
        promos = [m for m in got if len(m) == 5]
        eps = [m.uci() for m in board.legal_moves if board.is_en_passant(m)]
        castles_seen += len(castles)
        promos_seen += len(promos)
        eps_seen += len(eps)

        mark = "ok  " if ok else "FAIL"
        note = ""
        if castles:
            note += f" castle={','.join(sorted(castles))}"
        if promos:
            note += f" promo={len(promos)}"
        if eps:
            note += f" ep={','.join(sorted(eps))}"
        print(f"  {mark}  {tag:<34} {n:>3} legal{note}")
        for p in problems:
            print(f"        {p}")
        if not ok:
            failures += 1

    print()
    print(f"{len(positions)} positions, {failures} with a move-generation or encoding fault")
    print(f"castling moves generated and encoded: {castles_seen}")
    print(f"promotion moves generated and encoded: {promos_seen}")
    print(f"en-passant captures present in these positions: {eps_seen}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
