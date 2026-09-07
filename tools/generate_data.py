import chess
import chess.engine
import random
import numpy as np
import os
import multiprocessing

def get_base_fens():
    return [
        chess.STARTING_FEN,
        "r1bq1rk1/pp2ppbp/2np1np1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQK2R w KQ - 3 8",
        "r1bqkb1r/pp3ppp/2n1pn2/2pp4/3P4/2P1P1B1/PP1N1PPP/R2QKBNR b KQkq - 1 6",
        "rnbq1rk1/pp2bppp/4pn2/2pp4/2PP4/N4NP1/PP2PPBP/R1BQK2R w KQ - 0 7",
        "rnbqk1nr/bp3ppp/p7/3p4/P7/1N6/1PP2PPP/R1BQKBNR w KQkq - 2 8"
    ]

def generate_random_walks(num_games=1000):
    fens = get_base_fens()
    positions = set()
    
    for _ in range(num_games):
        start_fen = random.choice(fens)
        board = chess.Board(start_fen)
        
        # Vary random walk depth between 20 and 150 half-moves
        walk_length = random.randint(20, 150)
        
        for _ in range(walk_length):
            if board.is_game_over():
                break
                
            move = random.choice(list(board.legal_moves))
            board.push(move)
            
            # Skip if in check
            if board.is_check():
                continue
                
            # Get FEN without move counters for deduplication
            fen_parts = board.fen().split()
            core_fen = " ".join(fen_parts[:4])
            positions.add(core_fen)
            
    return list(positions)

def generate_pilot_data():
    os.makedirs("data", exist_ok=True)
    print("Generating random walk positions...")
    positions = generate_random_walks(2000) # Should be enough for ~50k unique positions
    print(f"Generated {len(positions)} unique positions.")
    
    # Cap at 50k
    if len(positions) > 50000:
        positions = random.sample(positions, 50000)
    
    with open("data/pilot_fens.txt", "w") as f:
        for p in positions:
            f.write(p + "\n")
    print(f"Saved {len(positions)} FENs to data/pilot_fens.txt")

if __name__ == "__main__":
    generate_pilot_data()
