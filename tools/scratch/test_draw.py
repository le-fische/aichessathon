import chess

def is_draw(board):
    if board.pawns or board.rooks or board.queens:
        return False
    knights = board.knights.bit_count()
    bishops = board.bishops.bit_count()
    if knights == 0 and bishops == 0:
        return True
    if knights == 1 and bishops == 0:
        return True
    if knights == 0 and bishops == 1:
        return True
    return False

print(is_draw(chess.Board("8/8/8/8/4k3/8/8/4K3 w - - 0 1")))
