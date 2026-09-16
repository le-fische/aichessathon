import shutil
from pathlib import Path
import hashlib

def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]

def snapshot(dest, changes=None):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    manifest = []
    
    # Files needed for engine
    files = ["agent.py", "bitboard.py", "evaluation.py", "nnue.py", "nsearch.py", "search.py"]
    for f in files:
        src = Path(f)
        if changes and f in changes:
            src = Path(changes[f])
            
        dest_file = dest / f
        shutil.copy2(src, dest_file)
        manifest.append(f"{hash_file(dest_file)} {f}")
        
    (dest / "__init__.py").touch()
    with open(dest / "manifest.txt", "w") as f:
        f.write("\n".join(manifest) + "\n")
    print(f"Created snapshot: {dest}")
    print("\n".join(manifest))
    print()

print("Match 1: Depth Instrument (12 games)")
# Side A: Old numba search (but using current bitboard, etc.)
snapshot("snapshots/match1_numba", {"nsearch.py": "baselines/numba_search_base/nsearch.py"})
# Side B: Python search (using current bitboard, etc.)
# We use current agent.py but flip the default to False, or just use python_search/agent.py!
# Wait, python_search/agent.py works but current agent.py already falls back if USE_NUMBA_SEARCH=False.
snapshot("snapshots/match1_python", {"agent.py": "baselines/python_search/agent.py"})

print("Match 2: Horizon Gate (60 games)")
# Side A: New numba search (current working tree)
snapshot("snapshots/match2_new")
# Side B: Old numba search (but using current bitboard)
snapshot("snapshots/match2_old", {"nsearch.py": "baselines/numba_search_base/nsearch.py"})

