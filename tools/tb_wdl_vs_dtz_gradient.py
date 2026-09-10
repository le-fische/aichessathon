"""WDL gives the search no gradient; DTZ does. Shown, not asserted.

For a won position, print every legal move with:
  - the score `search.get_evaluation` would return through the WDL probe
    (a flat 20000 - ply for every winning child)
  - the DTZ the same move leads to

If the WDL column is constant across moves that DTZ separates by dozens of
plies, the search has nothing to steer by. That is the whole of the
"blind to progress" defect, arriving through the tablebase rather than the
piece-square tables.

Usage:
    DTZ_DIR=~/…/tb-scratch/dtz34 python tools/tb_wdl_vs_dtz_gradient.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
import chess.syzygy

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WDL_DIR = os.path.join(REPO, "weights")
DTZ_DIR = os.path.expanduser(os.environ.get("DTZ_DIR", ""))

POSITIONS = [
    ("KBNvK, engine's shuffle", "7k/4BK2/8/5N2/8/8/8/8 w - - 80 41"),
    ("KBNvK, start", "8/8/8/4k3/8/8/8/1KBN4 w - - 0 1"),
    ("KQvKR, Philidor-ish", "8/8/8/3k4/7r/8/4Q3/4K3 w - - 0 1"),
]


def main():
    tb = chess.syzygy.open_tablebase(WDL_DIR)
    if DTZ_DIR:
        tb.add_directory(DTZ_DIR)

    ply = 4  # any fixed search ply; the point is that it does not vary by move
    for label, fen in POSITIONS:
        board = chess.Board(fen)
        print(f"\n{label}\n  {fen}")
        rows = []
        for mv in board.legal_moves:
            board.push(mv)
            try:
                child_wdl = tb.probe_wdl(board)
                child_dtz = tb.probe_dtz(board) if DTZ_DIR else None
            except Exception as exc:
                board.pop()
                rows.append((mv.uci(), f"({type(exc).__name__})", "-"))
                continue
            mate = board.is_checkmate()
            board.pop()
            # search.get_evaluation, from the CHILD's point of view, negated
            # back to the mover: a win for the mover is a loss for the child.
            if mate:
                wdl_score = "MATE"
            elif child_wdl < 0:
                wdl_score = f"{20000 - (ply + 1):.0f}"  # child loses -> we win
            elif child_wdl > 0:
                wdl_score = f"{-20000 + (ply + 1):.0f}"
            else:
                wdl_score = "0 (draw)"
            rows.append((mv.uci(), wdl_score, child_dtz))
        print(f"  {'move':<8}{'WDL-only score':>18}{'child dtz':>12}")
        for uci, w, d in sorted(rows, key=lambda r: str(r[2])):
            print(f"  {uci:<8}{str(w):>18}{str(d):>12}")
        distinct_wdl = {r[1] for r in rows}
        distinct_dtz = {r[2] for r in rows}
        print(f"  distinct WDL-only scores: {len(distinct_wdl)}   distinct dtz: {len(distinct_dtz)}")
    tb.close()


if __name__ == "__main__":
    main()
