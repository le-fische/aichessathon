import random
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import chess

from agent import get_move

# Hardcoded FENs
FENS = [
    # Curated opening positions from validation
    "r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8",
    "r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6",
    # Original test suite
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",  # start
    "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",  # en passant
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",  # kiwipete
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
    "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
    "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",  # promotion
    "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10",
    "7k/8/8/8/8/8/8/R3K3 w Q - 0 1",  # castling rights
    "8/8/8/8/8/7k/7p/7K w - - 0 1",  # stalemate
    "8/8/8/8/8/2k5/1p6/1K6 w - - 0 1",  # another stalemate
    "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1",
]


def generate_fens(count: int) -> list[str]:
    fens = set(FENS)
    while len(fens) < count:
        board = chess.Board()
        while not board.is_game_over() and len(fens) < count:
            fens.add(board.fen())
            legal_moves = list(board.legal_moves)
            if not legal_moves:
                break
            move = random.choice(legal_moves)
            board.push(move)
    return list(fens)[:count]


def test() -> None:
    fens = generate_fens(200)
    for fen in fens:
        board = chess.Board(fen)
        if not list(board.legal_moves):
            continue
        move_str = get_move(fen, 100)  # Fast budget for fuzzing
        try:
            move = chess.Move.from_uci(move_str)
            assert move in board.legal_moves, f"Illegal move {move_str} in {fen}"
        except ValueError as e:
            raise AssertionError(f"Malformed UCI move {move_str} in {fen}") from e

    print("Fuzzing passed 200 FENs")


if __name__ == "__main__":
    test()
