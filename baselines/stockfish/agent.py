import chess
import chess.engine
import atexit
import os

# Assuming stockfish is in PATH or specifically in /opt/homebrew/bin/stockfish
stockfish_path = "/opt/homebrew/bin/stockfish"

try:
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
except FileNotFoundError:
    # Fallback to just "stockfish" if the exact path isn't right on other machines
    engine = chess.engine.SimpleEngine.popen_uci("stockfish")

def cleanup():
    try:
        engine.quit()
    except Exception:
        pass

atexit.register(cleanup)

def get_move(fen: str, time_left_ms: int) -> str:
    board = chess.Board(fen)
    
    # Give stockfish a max of 0.1 seconds to think per move so tests run fast, 
    # but ensure we don't exceed the time limit if we're low on time.
    think_time = min(0.1, max(0.01, (time_left_ms / 1000.0) / 30))
    limit = chess.engine.Limit(time=think_time)
    
    # You can also use depth limit to weaken it for testing:
    # limit = chess.engine.Limit(depth=5)
    
    result = engine.play(board, limit)
    return result.move.uci()
