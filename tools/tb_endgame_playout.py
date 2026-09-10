"""Part A: does the WDL-only build actually finish won endgames, and how much
worse is it than a DTZ-optimal player?

Plays the LIVE numba build (agent.py -> nsearch.py -> bitboard.py) from a set of
won endgames, both sides, at a realistic per-move budget, and counts plies to a
recorded result. Then plays the same position with a DTZ-optimal winner against
a DTZ-optimal defender and counts plies to mate. The gap is what missing DTZ
costs.

Env:
    TIME_LEFT_MS   clock handed to get_move each ply (default 30000 -> ~1.75 s)
    MAX_PLIES      cap on the playout (default 120)
    DTZ_DIR        directory holding .rtbz files (needed for the optimal line)
    ONLY           comma-separated substring filter on position name

Usage:
    CHESSATHON_REQUIRE_NUMBA=1 DTZ_DIR=~/…/tb-scratch/dtz34 \
        python tools/tb_endgame_playout.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
import chess.syzygy

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WDL_DIR = os.path.join(REPO, "weights")
DTZ_DIR = os.path.expanduser(os.environ.get("DTZ_DIR", ""))

POSITIONS = [
    # name, fen, who is winning
    ("KRvK-round17", "4R3/8/8/3k1K2/8/8/8/8 w - - 15 83", chess.WHITE),
    ("KRvK-centre", "8/8/8/3k4/8/8/8/R3K3 w - - 0 1", chess.WHITE),
    ("KQvK-centre", "8/8/8/3k4/8/8/4Q3/4K3 w - - 0 1", chess.WHITE),
    ("KPvK-won", "8/8/8/8/3k4/8/3P4/3K4 w - - 0 1", chess.WHITE),
    ("KBNvK-corner", "8/8/8/4k3/8/8/8/1KBN4 w - - 0 1", chess.WHITE),
    ("KRvKP-won", "8/8/8/3k4/4p3/8/8/R3K3 w - - 0 1", chess.WHITE),
    ("KQvKR-won", "8/8/8/3k4/7r/8/4Q3/4K3 w - - 0 1", chess.WHITE),
    # round 31 shape: rook endgame, material on both sides, 5+ men -> outside
    # any tablebase we could ship
    ("KRPvKR-r31shape", "8/8/8/3k4/8/4P3/7r/R3K3 w - - 0 1", chess.WHITE),
    # second pass: KPvK-won above turned out to be a tablebase DRAW, and KBBvK
    # is the other two-minor mate.
    ("KPvK-reallywon", "8/8/4k3/8/8/4K3/4P3/8 w - - 0 1", chess.WHITE),
    ("KBBvK-corner", "8/8/8/4k3/8/8/8/1KBB4 w - - 0 1", chess.WHITE),
    ("KBNvK-b1start", "8/8/8/8/4k3/8/8/1KBN4 w - - 0 1", chess.WHITE),
]


def engine_playout(fen, max_plies, time_left_ms):
    import nsearch

    board = chess.Board(fen)
    nsearch.clear_tt()
    counts = {}
    key = None
    quiet = 0
    for ply in range(max_plies):
        if board.is_game_over(claim_draw=False):
            return board, board.outcome(claim_draw=False), ply, quiet
        if board.is_fivefold_repetition() or board.is_seventyfive_moves():
            return board, board.outcome(claim_draw=True), ply, quiet
        from nsearch import from_chess_board

        _p, _c, state = from_chess_board(board)
        key = state[4]
        counts[key] = counts.get(key, 0) + 1
        uci = nsearch.get_move(board, time_left_ms, counts)
        mv = chess.Move.from_uci(uci)
        if mv not in board.legal_moves:
            return board, f"ILLEGAL {uci}", ply, quiet
        if not (board.is_capture(mv) or board.piece_type_at(mv.from_square) == chess.PAWN):
            quiet += 1
        board.push(mv)
    return board, None, max_plies, quiet


def dtz_best_move(tb, board):
    """Winner: minimise dtz after the move. Defender: maximise it."""
    best = None
    best_key = None
    for mv in board.legal_moves:
        board.push(mv)
        try:
            if board.is_checkmate():
                child_wdl, child_dtz = -2, 0
            elif board.is_stalemate() or board.is_insufficient_material():
                child_wdl, child_dtz = 0, 0
            else:
                child_wdl = tb.probe_wdl(board)
                child_dtz = tb.probe_dtz(board)
        except Exception:
            board.pop()
            continue
        board.pop()
        # From the mover's point of view: the child's wdl is the OPPONENT's.
        our_wdl = -child_wdl
        # prefer higher our_wdl; among wins prefer smaller |dtz|
        key = (our_wdl, -abs(child_dtz) if our_wdl > 0 else abs(child_dtz))
        if best_key is None or key > best_key:
            best_key, best = key, mv
    return best


def dtz_playout(tb, fen, max_plies):
    board = chess.Board(fen)
    for ply in range(max_plies):
        if board.is_game_over(claim_draw=False):
            return board.outcome(claim_draw=False), ply
        mv = dtz_best_move(tb, board)
        if mv is None:
            return "no tb move", ply
        board.push(mv)
    return None, max_plies


def main():
    time_left_ms = int(os.environ.get("TIME_LEFT_MS", "30000"))
    max_plies = int(os.environ.get("MAX_PLIES", "120"))
    only = os.environ.get("ONLY", "")

    budget = min(time_left_ms * 0.045 + 400.0, time_left_ms * 0.25)
    print(f"time_left_ms={time_left_ms} -> nsearch budget {budget:.0f} ms per move")
    print(f"max_plies={max_plies}\n")

    tb = None
    if DTZ_DIR:
        tb = chess.syzygy.open_tablebase(WDL_DIR)
        tb.add_directory(DTZ_DIR)
        print(f"DTZ reference: {WDL_DIR} + {DTZ_DIR}\n")

    hdr = f"{'position':<18}{'wdl':>5}{'dtz':>6}{'opt plies':>11}{'engine plies':>14}{'quiet':>7}  outcome"
    print(hdr)
    print("-" * len(hdr))
    for name, fen, _winner in POSITIONS:
        if only and not any(k in name for k in only.split(",")):
            continue
        wdl = dtz = "-"
        opt = "-"
        if tb is not None:
            b = chess.Board(fen)
            try:
                wdl = tb.probe_wdl(b)
                dtz = tb.probe_dtz(b)
                out, n = dtz_playout(tb, fen, max_plies)
                opt = n if out is not None else f">{n}"
            except Exception as exc:
                wdl = dtz = f"({type(exc).__name__})"
        t0 = time.time()
        bf, out, n, quiet = engine_playout(fen, max_plies, time_left_ms)
        desc = "SHUFFLED, no result" if out is None else str(out)
        print(
            f"{name:<18}{str(wdl):>5}{str(dtz):>6}{str(opt):>11}{n:>14}{quiet:>7}  {desc}  [{time.time() - t0:.0f}s]"
        )
        if out is None:
            print(f"{'':<18}final: {bf.fen()}")
        sys.stdout.flush()

    if tb is not None:
        tb.close()


if __name__ == "__main__":
    main()
