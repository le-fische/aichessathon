"""Rebuild every gate snapshot from git, on any machine.

Nothing here depends on files that exist only on one laptop. Every snapshot is
derived from commits that are on GitHub, so a fresh clone plus

    git fetch upstream danny-test:danny-test
    uv run python tools/make_snapshots.py

reproduces byte-identical inputs to the ones the Mac gated. The manifests are
printed so the two machines can be compared directly.

Snapshots built:
    v11_control     the live v11 build: v10's evaluation, Danny's correctness search
    v11_contempt    control + CONTEMPT 25.0, so a winning engine stops shuffling
    v11_kingsafety  control + the king shelter term in both evaluations
    v11_terms34     control + rook on open file and doubled/isolated pawns
    v11_panic       control + Danny's panic-path fix
    v11_lmr         control + panic + LMR scaling and the history penalty
"""

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

MEMBERS = ("agent.py", "search.py", "evaluation.py", "bitboard.py", "nsearch.py")

# v10's shipped evaluation. Terms 3 and 4 are deliberately not in the control.
BASE = "c3736fd"
# Danny's correctness prefix: qsearch clock + TT abort guard + SEE + unwind.
V11_NSEARCH = "d27c6f7"
TERMS34 = "5197c06"      # rook open file + doubled/isolated pawns
PANIC = "5fb2495"        # panic path actually searches
LMR = "7b41bcc"          # LMR scaling + history penalty


def show(ref, path):
    result = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True)
    if result.returncode != 0:
        sys.exit(
            f"missing {ref}:{path}. Fetch Danny's branch first:\n"
            f"    git fetch upstream danny-test:danny-test"
        )
    return result.stdout


def write_manifest(dst):
    lines = [f"{hashlib.sha256((dst/n).read_bytes()).hexdigest()}  {n}" for n in MEMBERS]
    (dst / "manifest.txt").write_text("\n".join(lines) + "\n")
    print(f"  {dst.name}")
    for line in lines:
        print(f"    {line[:12]}  {line.split('  ')[1]}")


def build_control(dst, weights_src):
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "weights").mkdir(exist_ok=True)
    for name in ("agent.py", "search.py", "evaluation.py", "bitboard.py"):
        (dst / name).write_bytes(show(BASE, name))
    (dst / "nsearch.py").write_bytes(show(V11_NSEARCH, "nsearch.py"))
    for tb in sorted(weights_src.glob("*.rtbw")):
        shutil.copyfile(tb, dst / "weights" / tb.name)


def main():
    root = Path(".")
    snapshots = root / "snapshots"
    weights_src = root / "weights"
    if not any(weights_src.glob("*.rtbw")):
        sys.exit("weights/ holds no .rtbw tablebases; nothing to package")

    control = snapshots / "v11_control"
    build_control(control, weights_src)
    write_manifest(control)

    def derive(name):
        dst = snapshots / name
        build_control(dst, weights_src)
        return dst

    # contempt: one constant, in both searches
    dst = derive("v11_contempt")
    for name in ("nsearch.py", "search.py"):
        text = (dst / name).read_text()
        assert text.count("CONTEMPT = 0.0") == 1, f"{name}: CONTEMPT constant not unique"
        (dst / name).write_text(text.replace("CONTEMPT = 0.0", "CONTEMPT = 25.0"))
    write_manifest(dst)

    # king safety: the patcher writes both evaluations from the control
    dst = derive("v11_kingsafety")
    subprocess.run(
        [sys.executable, "tools/apply_king_safety.py", str(control), str(dst)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    for tb in sorted(weights_src.glob("*.rtbw")):
        shutil.copyfile(tb, dst / "weights" / tb.name)
    write_manifest(dst)

    # Terms 3 and 4 live only in the two evaluation files
    dst = derive("v11_terms34")
    for name in ("evaluation.py", "bitboard.py"):
        (dst / name).write_bytes(show(TERMS34, name))
    write_manifest(dst)

    # Danny's two held-back search changes
    for name, ref in (("v11_panic", PANIC), ("v11_lmr", LMR)):
        dst = derive(name)
        (dst / "nsearch.py").write_bytes(show(ref, "nsearch.py"))
        write_manifest(dst)


if __name__ == "__main__":
    main()
