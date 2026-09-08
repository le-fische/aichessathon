import chess
import chess.engine
import random
import sys
import os

sys.path.append('.')
import nsearch

def run(total_positions=2_000_000, shard_size=100_000):
    stockfish_path = "baselines/stockfish/stockfish/stockfish-macos-m1-apple-silicon"
    if not os.path.exists(stockfish_path):
        print("Stockfish not found!")
        return
        
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    os.makedirs("data/shards", exist_ok=True)
    
    positions_generated = 0
    games = 0
    
    print(f"Generating {total_positions} positions in shards of {shard_size}...", flush=True)
    
    shard_idx = 0
    while positions_generated < total_positions:
        shard_file = f"data/shards/dataset_shard_{shard_idx:03d}.csv"
        # Skip if shard already exists
        if os.path.exists(shard_file):
            print(f"Shard {shard_idx} exists, skipping...", flush=True)
            shard_idx += 1
            positions_generated += shard_size
            continue
            
        print(f"Starting shard {shard_idx}...", flush=True)
        shard_positions = 0
        
        with open(shard_file, "w") as f:
            f.write("fen,score\n")
            
            while shard_positions < shard_size:
                board = chess.Board()
                games += 1
                pos_counts = {}
                
                while not board.is_game_over(claim_draw=True) and board.fullmove_number < 150:
                    is_q = not board.is_check() and not any(board.is_capture(m) for m in board.legal_moves)
                    
                    if is_q and random.random() < 0.5:
                        info = engine.analyse(board, chess.engine.Limit(depth=8))
                        score = info["score"].relative.score(mate_score=10000)
                        f.write(f"{board.fen()},{score}\n")
                        shard_positions += 1
                        positions_generated += 1
                        
                        if shard_positions % 1000 == 0:
                            print(f"Shard {shard_idx}: {shard_positions} / {shard_size} positions... (Game {games})", flush=True)
                            f.flush()
                        if shard_positions >= shard_size:
                            break
                            
                    if random.random() < 0.1:
                        move = random.choice(list(board.legal_moves))
                    else:
                        try:
                            move_str, _, _ = nsearch.get_move_with_info(board.copy(), 1000, pos_counts, max_depth=4)
                            move = chess.Move.from_uci(move_str)
                        except Exception:
                            move = random.choice(list(board.legal_moves))
                    board.push(move)
                    
        shard_idx += 1
        
    engine.quit()
    print("Done generating 2M positions.", flush=True)

if __name__ == "__main__":
    run()
