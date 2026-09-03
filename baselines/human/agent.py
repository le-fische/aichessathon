import chess

def get_move(fen: str, time_left_ms: int) -> str:
    board = chess.Board(fen)
    print(f"\nTime left: {time_left_ms} ms")
    print(board)
    print()
    while True:
        try:
            move_str = input("Enter your move (UCI format, e.g. e2e4): ").strip()
            move = chess.Move.from_uci(move_str)
            if move in board.legal_moves:
                return move_str
            else:
                print("Illegal move on this board, try again.")
        except ValueError:
            print("Invalid UCI format, try again. (e.g. e2e4, e7e8q)")
        except EOFError:
            import sys
            sys.exit(0)
