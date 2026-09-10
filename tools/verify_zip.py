"""Verify that a built submission zip faithfully represents its source.

This answers one question and deliberately not more: **is this zip a current, complete
copy of the source it claims to be built from?** It catches the mistake it was written
for on 2026-09-05 -- you edit ``agent.py``, forget to rebuild ``submission.zip``, and
upload yesterday's engine -- plus a zip built from a different tree, or built before a
``weights/`` file was added.

It is NOT the file-set gate. Deciding *which* files belong in the submission is
``tools/preflight.py`` check C02, which compares against a curated allowlist. That
distinction matters: deriving the expected member set from ``harness.package``'s own
glob would make the check tautological, because the zip was built by that same glob from
that same tree -- a scratch ``.py`` left at the repo root would appear in both and pass.
That is exactly the failure the script should catch, and HANDOFF house rule 3 says a
check that cannot fail is not a check.

Usage::

    python tools/verify_zip.py                       # submission.zip against HEAD
    python tools/verify_zip.py --against worktree    # ... against the working tree
    python tools/verify_zip.py --zip /tmp/other.zip

``--against HEAD`` is the default because HANDOFF's upload checklist requires the zip be
built from ``git show HEAD:<file>``, never from a dirty working tree.

Exit status is 0 when every check passes and 1 otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from harness.package import DEFAULT_INCLUDES, members  # noqa: E402

SKIP_PARTS = {"__pycache__", ".DS_Store"}


def git_blob(repo: Path, path: str) -> bytes:
    """Bytes of ``path`` as recorded in HEAD."""
    result = subprocess.run(
        ["git", "cat-file", "blob", f"HEAD:{path}"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    return result.stdout


def head_submission_paths(repo: Path) -> list[str]:
    """Replicate harness.package's member selection over the HEAD tree.

    Mirrors ``tools/preflight.py``'s helper of the same name; kept here so this script
    stands alone if preflight is ever refactored.
    """
    listed = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    chosen: list[str] = []
    for path in listed:
        parts = path.split("/")
        if SKIP_PARTS & set(parts):
            continue
        if (len(parts) == 1 and path.endswith(".py")) or parts[0] == "weights":
            chosen.append(path)
    return sorted(chosen)


def worktree_sources(repo: Path) -> dict[str, bytes]:
    """What harness.package would ship right now, read from the working tree."""
    return {name: path.read_bytes() for path, name in members(repo, DEFAULT_INCLUDES)}


def head_sources(repo: Path) -> dict[str, bytes]:
    """What harness.package would ship from the HEAD tree."""
    return {path: git_blob(repo, path) for path in head_submission_paths(repo)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify a submission zip against its source. See module docstring.",
    )
    parser.add_argument(
        "--zip",
        type=Path,
        default=REPO / "submission.zip",
        help="zip to verify (default: submission.zip at the repo root)",
    )
    parser.add_argument(
        "--against",
        choices=("HEAD", "worktree"),
        default="HEAD",
        help="source to compare against (default: HEAD, per HANDOFF's upload checklist)",
    )
    arguments = parser.parse_args()

    zip_path: Path = arguments.zip
    if not zip_path.exists():
        print(f"ERROR: {zip_path} not found. Build it first:", file=sys.stderr)
        print("  python -m harness.package", file=sys.stderr)
        return 1

    source = head_sources(REPO) if arguments.against == "HEAD" else worktree_sources(REPO)

    with zipfile.ZipFile(zip_path) as archive:
        infos = [i for i in archive.infolist() if not i.is_dir()]
        contents = {i.filename: archive.read(i.filename) for i in infos}

    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    unzipped = sum(len(b) for b in contents.values())

    # --- Check C: provenance, printed so it can be pasted into a run log -----------
    print(f"zip        {zip_path}")
    print(f"sha256     {digest}")
    print(f"members    {len(contents)}")
    print(f"unzipped   {unzipped:,} bytes")
    print(f"against    {arguments.against} ({len(source)} source files)")
    print()

    failures: list[str] = []

    # --- Check A: every member matches its source ---------------------------------
    stale: list[str] = []
    orphans: list[str] = []
    for name, blob in sorted(contents.items()):
        expected = source.get(name)
        if expected is None:
            orphans.append(name)
        elif expected != blob:
            stale.append(name)

    if orphans:
        failures.append(f"{len(orphans)} member(s) with no counterpart in {arguments.against}")
        print(f"FAIL  {len(orphans)} member(s) not present in {arguments.against}:")
        for name in orphans:
            print(f"        {name}")
    if stale:
        failures.append(f"{len(stale)} stale member(s)")
        print(f"FAIL  {len(stale)} member(s) differ from {arguments.against} (stale zip):")
        for name in stale:
            print(f"        {name}  zip {len(contents[name]):,}B vs source {len(source[name]):,}B")
    if not orphans and not stale:
        print(f"ok    all {len(contents)} members are byte-identical to {arguments.against}")

    # --- Check B: nothing the source would ship is missing ------------------------
    missing = sorted(set(source) - set(contents))
    if missing:
        failures.append(f"{len(missing)} source file(s) absent from the zip")
        print(f"FAIL  {len(missing)} file(s) {arguments.against} would ship are not in the zip:")
        for name in missing:
            print(f"        {name}")
    else:
        print(f"ok    every file {arguments.against} would ship is present")

    print()
    print("This is a provenance check only. For the file-set gate (unexpected root .py,")
    print("shadowed module names, native binaries, dead weights, size, imports) run:")
    print("  python tools/preflight.py")
    print()

    if failures:
        print("FAILED: " + "; ".join(failures))
        return 1
    print("Zip verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
