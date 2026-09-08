"""Trace what the engine actually plays from round 17's winning endgame."""
import os
import sys

sys.path.insert(0, os.path.expanduser("~/scratch/ab"))
os.environ.pop("SEARCH_MAX_NODES", None)

import chess

import evaluation
import search

START = "rnbq1rk1/ppp2ppp/4pn2/8/1bBP4/2N1P2P/PP3PP1/R1BQK1NR b KQ - 0 7"
san = open(os.path.expanduser("~/scratch/game17.san")).read().split()
board = chess.Board(START)
for tok in san:
    board.push_san(tok)
    if len(board.piece_map()) == 3:
        break

print(f"start {board.fen()}   turn={'white' if board.turn else 'black'}")
seen = {}
for ply in range(24):
    if board.is_game_over(claim_draw=True):
        print("game over:", board.outcome(claim_draw=True).termination.name)
        break
    if board.turn == chess.WHITE:
        uci = search.get_move(board, 18_200)
        mv = chess.Move.from_uci(uci)
        san_mv = board.san(mv)
        board.push(mv)
        ev = evaluation.evaluate(board)
        wk, bk = board.king(chess.WHITE), board.king(chess.BLACK)
        edge = min(chess.square_file(bk), 7 - chess.square_file(bk)) + min(
            chess.square_rank(bk), 7 - chess.square_rank(bk))
        kdist = max(abs(chess.square_file(wk) - chess.square_file(bk)),
                    abs(chess.square_rank(wk) - chess.square_rank(bk)))
        print(f"  W {san_mv:<6} depth {search.completed_depth:>2}  eval {ev:+7.0f}  "
              f"blackking-to-edge {edge}  king-distance {kdist}")
    else:
        best, best_d = None, -1
        for m in board.legal_moves:
            board.push(m)
            sq = board.king(chess.BLACK)
            d = min(chess.square_file(sq), 7 - chess.square_file(sq)) + min(
                chess.square_rank(sq), 7 - chess.square_rank(sq))
            board.pop()
            if d > best_d:
                best_d, best = d, m
        print(f"  B {board.san(best)}")
        board.push(best)
    k = board._transposition_key()
    seen[k] = seen.get(k, 0) + 1
    if seen[k] >= 3:
        print(f"  *** threefold at ply {ply+1}: {board.fen()}")
        break
