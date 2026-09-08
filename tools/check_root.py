# ruff: noqa
#!/usr/bin/env python3
import os
import sys

# Root files only: harness/package.py sweeps every root *.py into the zip, so a
# stray scratch script ships with the submission. That has happened six times.
# bitboard.py, nnue.py and nsearch.py are in-progress modules that must live at
# the root to be packageable later; none of them is imported by agent.py yet, and
# the submission zip is built from a staging directory holding only the three
# engine files, so they do not ship until they are wired in deliberately.
ALLOWED_PY_FILES = {
    "agent.py",
    "search.py",
    "evaluation.py",
    "bitboard.py",
    "nnue.py",
    "nsearch.py",
    "nsearch_nnue.py",
}


def check_root():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    py_files = {f for f in os.listdir(root_dir) if f.endswith(".py")}

    unallowed = py_files - ALLOWED_PY_FILES
    binaries = {f for f in os.listdir(root_dir) if f.endswith((".so", ".pyd", ".dylib", ".bin"))}

    if unallowed or binaries:
        print("ERROR: Contaminated repo root!", file=sys.stderr)
        if unallowed:
            print(f"Unallowed python files: {', '.join(unallowed)}", file=sys.stderr)
            print(
                f"Allowed python files are exactly: {', '.join(ALLOWED_PY_FILES)}", file=sys.stderr
            )
        if binaries:
            print(f"Unallowed compiled binaries: {', '.join(binaries)}", file=sys.stderr)
        sys.exit(1)

    print("Repo root check passed.", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    check_root()
