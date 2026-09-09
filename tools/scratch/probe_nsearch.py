"""Probe nsearch.get_move DIRECTLY, bypassing agent.py's safety net.

agent.py validates whatever nsearch returns against python-chess and quietly
substitutes a legal move if it is wrong, so probe_agent.py cannot see a
move-generation bug in the numba path unless CHESSATHON_REQUIRE_NUMBA=1 is
set and the stderr is read. This calls nsearch directly so the raw string is
the thing under test.
"""

from __future__ import annotations

import collections
import os
import sys
import time
import traceback

import chess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import nsearch  # noqa: E402
from bitboard import from_chess_board  # noqa: E402
from fen_suite import all_cases  # noqa: E402

PANIC_FLOOR_MS = 100
SLACK_MS = 2000


def main() -> int:
    bad = 0
    terminal = 0
    for i, case in enumerate(all_cases()):
        board = chess.Board(case.fen)
        counts: collections.Counter = collections.Counter()
        _p, _c, state = from_chess_board(board)
        counts[state[4]] += 1

        budget = max(case.time_left_ms, PANIC_FLOOR_MS) + (SLACK_MS if i == 0 else 0)
        t0 = time.perf_counter()
        try:
            raw = nsearch.get_move(board, case.time_left_ms, counts)
        except Exception:
            dt = (time.perf_counter() - t0) * 1000
            if not any(board.legal_moves):
                terminal += 1
                print(f"  RAISE(terminal) {case.id:<34} {dt:>8.1f}ms  "
                      f"{traceback.format_exc().strip().splitlines()[-1]}")
            else:
                bad += 1
                print(f"  CRASH      {case.id:<34} {dt:>8.1f}ms")
                print(traceback.format_exc())
            continue
        dt = (time.perf_counter() - t0) * 1000

        status = "ok  "
        detail = ""
        if not isinstance(raw, str):
            status, detail = "TYPE", f"{type(raw).__name__} {raw!r}"
        else:
            try:
                mv = chess.Move.from_uci(raw)
            except ValueError as exc:
                status, detail = "MALFORMED", str(exc)
            else:
                if mv not in board.legal_moves:
                    pseudo = mv in board.pseudo_legal_moves
                    status = "ILLEGAL"
                    detail = "leaves king in check" if pseudo else "not pseudo-legal"
                elif case.illegal_moves and raw in case.illegal_moves:
                    status, detail = "ILLEGAL", "on the case's illegal list"
                elif case.must_choose and raw not in case.must_choose:
                    status, detail = "WRONG", f"expected one of {case.must_choose}"
                elif dt > budget:
                    status, detail = "FLAG", f"budget {budget}ms"

        if status not in ("ok  ",):
            bad += 1
        print(f"  {status:<10} {case.id:<34} {dt:>8.1f}ms  -> {raw}  {detail}")

    print(f"\n{len(all_cases())} cases, {bad} faults, "
          f"{terminal} raises in positions with zero legal moves")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
