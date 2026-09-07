import chess
import chess.engine
import numpy as np
import multiprocessing
import os

STOCKFISH_PATH = "stockfish"

def label_worker(fens_chunk, worker_id):
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    results = []
    
    for fen in fens_chunk:
        board = chess.Board(fen)
        try:
            info = engine.analyse(board, chess.engine.Limit(depth=10))
            score = info["score"].white()
            
            if score.is_mate():
                continue # Skip mate scores
            
            cp = score.score()
            # Clamp to +/- 2000
            cp = max(-2000, min(2000, cp))
            
            # Save features as (FEN, cp)
            results.append((fen, cp))
        except Exception as e:
            pass
            
    engine.quit()
    return results

def label_data():
    with open("data/pilot_fens.txt", "r") as f:
        fens = [line.strip() for line in f]
        
    print(f"Labeling {len(fens)} FENs with Stockfish...")
    
    num_cores = multiprocessing.cpu_count()
    chunk_size = len(fens) // num_cores + 1
    chunks = [fens[i:i + chunk_size] for i in range(0, len(fens), chunk_size)]
    
    with multiprocessing.Pool(num_cores) as pool:
        results = pool.starmap(label_worker, [(chunk, i) for i, chunk in enumerate(chunks)])
        
    labeled = []
    for r in results:
        labeled.extend(r)
        
    print(f"Labeled {len(labeled)} positions. Skipped mates.")
    
    # Save to npz
    out_fens = np.array([x[0] for x in labeled])
    out_scores = np.array([x[1] for x in labeled], dtype=np.float32)
    
    np.savez_compressed("data/pilot_labeled.npz", fens=out_fens, scores=out_scores)
    print("Saved to data/pilot_labeled.npz")

if __name__ == "__main__":
    if not os.path.exists(STOCKFISH_PATH):
        # find stockfish executable
        import glob
        matches = glob.glob("baselines/stockfish/stockfish*")
        if matches:
            STOCKFISH_PATH = matches[0]
            
    label_data()
