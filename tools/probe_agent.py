"""Run an agent's get_move against the adversarial suite.

Usage:
    python probe_agent.py                      # expects agent.py importable
    python probe_agent.py --agent path/to/agent.py
    python probe_agent.py --only legality      # filter by tag
    python probe_agent.py --json out.json

What this checks, in the order the competition cares about:

  1. get_move returns without raising. An exception is a crash, a crash is a loss.
  2. The return value is a str. Not a Move, not None, not bytes.
  3. It parses as UCI and is legal in the given position. Illegal is a loss.
  4. It is not a move the case declares illegal by construction.
  5. It came back inside its time budget. Overshooting is a flag, a flag is a loss.
  6. It did not write to the real stdout. Per the docs the runner points fd 1
     at stderr before importing the agent, so printing is safe for the
     protocol, but every byte still costs I/O time on a single 2.6 GHz core.

The harness deliberately does NOT judge move quality except where a case
declares must_choose / must_not_choose, because a legal bad move costs you
rating and an illegal good move costs you the whole game.
"""

import argparse
import importlib.util
import io
import json
import os
import sys
import time
import traceback
from contextlib import redirect_stdout

import chess

from fen_suite import all_cases, validate

# The runner gives 120s + 0.5s/move on one core of an EPYC 9V74 at 2.60 GHz.
# Anything that takes longer than the clock it was handed would have flagged.
# We add a little slack for import warm-up on the first call only.
FIRST_CALL_SLACK_MS = 2_000

# Below this, the clock is already effectively gone and the runner is about to
# flag us whatever we do. The question in the panic cases is not "did it beat
# the budget" but "did it return promptly instead of hanging or crashing", so
# we hold the timing bar at this floor rather than at an unmeetable 0 ms.
PANIC_FLOOR_MS = 100


class Result:
    __slots__ = ("case", "status", "move", "elapsed_ms", "detail", "stdout_bytes")

    def __init__(self, case):
        self.case = case
        self.status = "pass"
        self.move = None
        self.elapsed_ms = 0.0
        self.detail = ""
        self.stdout_bytes = 0

    def fail(self, status, detail):
        self.status = status
        self.detail = detail
        return self


def load_agent(path):
    """Import the agent module the way the runner does."""
    if path is None:
        import agent  # noqa: F401

        return agent

    path = os.path.abspath(path)
    directory = os.path.dirname(path)
    if directory not in sys.path:
        sys.path.insert(0, directory)
    spec = importlib.util.spec_from_file_location("agent_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def probe(agent_module, case, first_call=False):
    result = Result(case)
    board = chess.Board(case.fen)

    budget_ms = max(case.time_left_ms, PANIC_FLOOR_MS) + (
        FIRST_CALL_SLACK_MS if first_call else 0
    )
    captured = io.StringIO()

    start = time.perf_counter()
    try:
        with redirect_stdout(captured):
            raw = agent_module.get_move(case.fen, case.time_left_ms)
    except Exception:
        result.elapsed_ms = (time.perf_counter() - start) * 1000
        result.stdout_bytes = len(captured.getvalue())
        return result.fail("CRASH", traceback.format_exc(limit=6).strip())
    result.elapsed_ms = (time.perf_counter() - start) * 1000
    result.stdout_bytes = len(captured.getvalue())

    # A position with no legal moves is a special case: the runner should not
    # ask, and returning nothing is defensible. Not crashing is the whole test.
    if not any(board.legal_moves):
        if raw is None:
            return result
        # Fall through and still check the type, since returning junk here
        # would be a bug if the runner ever did ask.

    if raw is None:
        return result.fail("NONE", "returned None in a position with legal moves")

    if not isinstance(raw, str):
        return result.fail("TYPE", f"returned {type(raw).__name__}, expected str: {raw!r}")

    result.move = raw

    stripped = raw.strip()
    if stripped != raw:
        result.fail("WHITESPACE", f"returned {raw!r} with surrounding whitespace")

    try:
        move = chess.Move.from_uci(stripped)
    except ValueError as exc:
        return result.fail("MALFORMED", f"{stripped!r} is not UCI: {exc}")

    if move not in board.legal_moves:
        # Distinguish the two ways this goes wrong, because they point at
        # completely different bugs.
        pseudo = move in board.pseudo_legal_moves
        kind = "leaves own king in check" if pseudo else "not even pseudo-legal"
        return result.fail("ILLEGAL", f"{stripped} is illegal here ({kind})")

    if case.illegal_moves and stripped in case.illegal_moves:
        return result.fail("ILLEGAL", f"{stripped} is on this case's illegal list")

    if case.must_choose and stripped not in case.must_choose:
        return result.fail(
            "WRONG_MOVE", f"returned {stripped}, expected one of {case.must_choose}"
        )

    if case.must_not_choose and stripped in case.must_not_choose:
        return result.fail("BLUNDER", f"returned {stripped}, which this case forbids")

    if result.elapsed_ms > budget_ms:
        return result.fail(
            "FLAG",
            f"took {result.elapsed_ms:.0f}ms with {case.time_left_ms}ms on the clock "
            f"(bar was {budget_ms}ms)",
        )

    return result


LOSS_STATUSES = {"CRASH", "ILLEGAL", "MALFORMED", "NONE", "TYPE", "FLAG"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", default=None, help="path to agent.py")
    parser.add_argument("--only", default=None, help="run only cases with this tag or category")
    parser.add_argument("--json", default=None, help="write full results to this file")
    parser.add_argument("--quiet", action="store_true", help="only print failures")
    args = parser.parse_args()

    issues = validate()
    if issues:
        print("Refusing to run: the suite itself is invalid.", file=sys.stderr)
        for line in issues:
            print("  -", line, file=sys.stderr)
        return 2

    cases = all_cases()
    if args.only:
        needle = args.only.lower()
        cases = [c for c in cases if needle == c.category.lower() or needle in [t.lower() for t in c.tags]]
        if not cases:
            print(f"No cases match {args.only!r}", file=sys.stderr)
            return 2

    try:
        agent_module = load_agent(args.agent)
    except Exception:
        print("Could not import the agent at all. That is itself the bug:", file=sys.stderr)
        traceback.print_exc()
        return 2

    if not hasattr(agent_module, "get_move"):
        print("Agent module has no get_move. The runner requires it.", file=sys.stderr)
        return 2

    results = []
    for i, case in enumerate(cases):
        res = probe(agent_module, case, first_call=(i == 0))
        results.append(res)
        if res.status != "pass" or not args.quiet:
            mark = "ok  " if res.status == "pass" else res.status
            line = f"  {mark:<10} {case.id:<34} {res.elapsed_ms:>8.1f}ms"
            if res.move:
                line += f"  -> {res.move}"
            print(line)
            if res.detail:
                for dl in res.detail.splitlines():
                    print(f"             {dl}")

    losses = [r for r in results if r.status in LOSS_STATUSES]
    soft = [r for r in results if r.status not in LOSS_STATUSES and r.status != "pass"]
    noisy = [r for r in results if r.stdout_bytes > 0]

    print()
    print(f"{len(results)} cases, {len(losses)} that would lose a rated game, {len(soft)} soft failures")
    if losses:
        print("\nWould lose a rated game:")
        for r in losses:
            print(f"  {r.status:<10} {r.case.id}")
            print(f"             {r.case.why}")
    if soft:
        print("\nSoft failures:")
        for r in soft:
            print(f"  {r.status:<10} {r.case.id}: {r.detail}")
    if noisy:
        total = sum(r.stdout_bytes for r in noisy)
        print(
            f"\n{len(noisy)} cases wrote {total} bytes to stdout. Harmless for the "
            "protocol (the runner repoints fd 1 at stderr) but it is I/O time on "
            "every move of every rated game."
        )

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(
                [
                    {
                        "id": r.case.id,
                        "category": r.case.category,
                        "tags": r.case.tags,
                        "fen": r.case.fen,
                        "time_left_ms": r.case.time_left_ms,
                        "status": r.status,
                        "move": r.move,
                        "elapsed_ms": round(r.elapsed_ms, 2),
                        "stdout_bytes": r.stdout_bytes,
                        "detail": r.detail,
                        "why": r.case.why,
                    }
                    for r in results
                ],
                fh,
                indent=2,
            )
        print(f"\nwrote {args.json}")

    return 1 if losses else 0


if __name__ == "__main__":
    sys.exit(main())
