#!/usr/bin/env python3
import os
import sys

ALLOWED_PY_FILES = {"agent.py", "search.py", "evaluation.py", "bitboard.py"}


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
