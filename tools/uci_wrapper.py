#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from agent import get_move


def main():
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    while True:
        try:
            line = sys.stdin.readline()
        except EOFError:
            break

        if not line:
            break

        line = line.strip()
        if not line:
            continue

        parts = line.split()
        cmd = parts[0]

        if cmd == "uci":
            print("id name AI Chessathon Agent")
            print("id author You")
            print("uciok")
            sys.stdout.flush()
        elif cmd == "isready":
            print("readyok")
            sys.stdout.flush()
        elif cmd == "position":
            if "startpos" in parts:
                fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
                moves_idx = parts.index("moves") if "moves" in parts else -1
                if moves_idx != -1:
                    import chess

                    board = chess.Board(fen)
                    for m in parts[moves_idx + 1 :]:
                        board.push_uci(m)
                    fen = board.fen()
            elif "fen" in parts:
                fen_idx = parts.index("fen")
                fen = " ".join(parts[fen_idx + 1 : fen_idx + 7])
                moves_idx = parts.index("moves") if "moves" in parts else -1
                if moves_idx != -1:
                    import chess

                    board = chess.Board(fen)
                    for m in parts[moves_idx + 1 :]:
                        board.push_uci(m)
                    fen = board.fen()
        elif cmd == "go":
            time_left_ms = 120_000  # default
            try:
                import chess

                board = chess.Board(fen)
                if board.turn == chess.WHITE and "wtime" in parts:
                    idx = parts.index("wtime")
                    time_left_ms = int(parts[idx + 1])
                elif board.turn == chess.BLACK and "btime" in parts:
                    idx = parts.index("btime")
                    time_left_ms = int(parts[idx + 1])
            except Exception:
                pass

            move = get_move(fen, time_left_ms)
            print(f"bestmove {move}")
            sys.stdout.flush()
        elif cmd == "quit":
            break


if __name__ == "__main__":
    main()
