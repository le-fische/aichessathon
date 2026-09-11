import chess
print(f"White 7th rank: {hex(0x00FF000000000000)}")
print(f"Black 7th rank: {hex(0x000000000000FF00)}")
print("Squares on rank 2:", [chess.SQUARE_NAMES[sq] for sq in chess.SQUARES if (1<<sq) & 0x000000000000FF00])
