import hashlib
import sys
from pathlib import Path

def print_dir(d):
    print(f"Snapshot: {d}")
    for p in sorted(Path(d).glob("*.py")):
        sha = hashlib.sha256(p.read_bytes()).hexdigest()[:8]
        print(f"  {sha} {p.name}")

print_dir("snapshots/match1_a")
print_dir("snapshots/match1_b")
print_dir("snapshots/match2_a")
print_dir("snapshots/match2_b")
