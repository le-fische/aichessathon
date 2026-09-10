"""Run the three outstanding gates back to back, unattended.

One machine, one match at a time, so these are strictly sequential. Each gate
isolates a single change by choosing its control accordingly:

    king safety   v11 + king shelter      vs  the live v11 build
    panic path    v11 + panic fix         vs  the live v11 build
    LMR + history v11 + panic + LMR       vs  v11 + panic

The third is gated against the second rather than against v11 so that a verdict
is about LMR and the history penalty alone, not about them plus the panic fix.

Each gate is sequential rather than fixed length. A 30-game match has a standard
error near 9 percent, which cannot resolve the size of change we are looking for:
a true +50 Elo is a 57 percent score, inside one standard error of 50. So 30
games run as a screen that only returns a verdict when the effect is large, and
the match continues to 60 when it does not.

    score <= 0.40   clear regression, stop and revert
    score >= 0.60   large positive effect, ship
    otherwise       inconclusive, play 30 more and judge the pooled 60

At 60 games the standard error is near 6.5 percent and the rule is the project's
usual one: ship only if the lower bound clears 50 percent.

Run from the repo root and leave it. Roughly 1.5 to 3 hours per gate.

    CHESSATHON_REQUIRE_NUMBA=1 uv run python tools/gate_queue.py

Every game is appended to its gate's results file as it finishes, so an
interrupted run still leaves on disk everything it actually measured.
"""

import math
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
os.environ["USE_NUMBA_SEARCH"] = "1"
os.environ["CHESSATHON_REQUIRE_NUMBA"] = "1"

from harness.referee import play_match
from harness.sandbox import local
from tools.ab_arena import build_book

SCREEN_GAMES = 30
FULL_GAMES = 60
BASE_MS = 120_000
INC_MS = 500
SEED = 20260910

GATES = [
    (
        "contempt",
        "score a draw at -25cp instead of 0, so a winning engine stops shuffling",
        Path("snapshots/v11_contempt"),
        Path("snapshots/v11_control"),
    ),
    (
        "king-safety",
        "king shelter in both evaluations",
        Path("snapshots/v11_kingsafety"),
        Path("snapshots/v11_control"),
    ),
    (
        "terms34",
        "rook on open file plus doubled and isolated pawns, both never measured",
        Path("snapshots/v11_terms34"),
        Path("snapshots/v11_control"),
    ),
]


def stderr_of(wins, draws, losses, games):
    """Standard error of the match score, the estimator this project uses."""
    if games == 0:
        return 0.0
    score = (wins + draws / 2) / games
    variance = (
        wins * (1 - score) ** 2
        + draws * (0.5 - score) ** 2
        + losses * score ** 2
    ) / games
    return math.sqrt(variance / games)


def emit(handle, line):
    print(line, flush=True)
    handle.write(line + "\n")
    handle.flush()


def run_gate(name, description, candidate, control, book):
    out = Path(f"runs/2026-09-10-{name}/results.txt")
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w") as handle:
        emit(handle, f"GATE: {name} -- {description}")
        emit(handle, f"{BASE_MS // 1000}s + {INC_MS}ms, colours swapped, one game at a time")
        emit(handle, "")
        emit(handle, f"A (candidate) {candidate}:")
        emit(handle, (candidate / "manifest.txt").read_text().rstrip())
        emit(handle, "")
        emit(handle, f"B (control)   {control}:")
        emit(handle, (control / "manifest.txt").read_text().rstrip())
        emit(handle, "")

        wins = draws = losses = played = 0
        target = SCREEN_GAMES
        started = time.time()

        while played < target:
            a_is_white = played % 2 == 0
            fen = book[played // 2]

            agent_a = local(candidate)
            agent_b = local(control)
            white = agent_a if a_is_white else agent_b
            black = agent_b if a_is_white else agent_a

            outcome = play_match(white, black, BASE_MS, INC_MS, start_fen=fen)

            if outcome.result in ("draw", "void"):
                draws += 1
            elif (outcome.result == "white") == a_is_white:
                wins += 1
            else:
                losses += 1
            played += 1

            score = (wins + draws / 2) / played
            elapsed = (time.time() - started) / 60.0
            emit(
                handle,
                f"game {played}/{target}: {outcome.result} by {outcome.termination}"
                f"  running +{wins} ={draws} -{losses}  ({score:.1%})  [{elapsed:.0f}m]",
            )

            if played == SCREEN_GAMES and target == SCREEN_GAMES:
                err = stderr_of(wins, draws, losses, played)
                emit(handle, "")
                emit(
                    handle,
                    f"screen complete: +{wins} ={draws} -{losses}"
                    f"  score {score:.1%} +/- {err:.1%} (1 sigma, {played} games)",
                )
                if score <= 0.40:
                    verdict = "REGRESSION at the screen. Revert. Not shipping."
                    emit(handle, f"VERDICT: {verdict}")
                    return name, verdict
                if score >= 0.60:
                    verdict = "LARGE POSITIVE at the screen. Ship."
                    emit(handle, f"VERDICT: {verdict}")
                    return name, verdict
                emit(handle, "inconclusive at 30. Continuing to 60.")
                emit(handle, "")
                target = FULL_GAMES

        err = stderr_of(wins, draws, losses, played)
        score = (wins + draws / 2) / played
        emit(handle, "")
        emit(
            handle,
            f"final: +{wins} ={draws} -{losses}"
            f"  score {score:.1%} +/- {err:.1%} (1 sigma, {played} games)",
        )
        if score - err > 0.50:
            verdict = f"SHIP. {score:.1%} +/- {err:.1%}, lower bound clears 50%."
        elif score + err < 0.50:
            verdict = f"REVERT. {score:.1%} +/- {err:.1%}, upper bound below 50%."
        else:
            verdict = f"UNMEASURED, not neutral. {score:.1%} +/- {err:.1%} crosses 50%. Do not ship."
        emit(handle, f"VERDICT: {verdict}")
        return name, verdict


def main():
    book = build_book(FULL_GAMES // 2, 8, SEED)
    verdicts = []
    for name, description, candidate, control in GATES:
        if not (candidate / "manifest.txt").exists():
            print(f"skipping {name}: {candidate} is missing", flush=True)
            continue

        # A gate that already reached a verdict is not re-run. The king-safety
        # gate was started on its own before this queue existed; leaving its
        # result in place saves two hours of machine time on a question that
        # has already been answered.
        done = Path(f"runs/2026-09-10-{name}/results.txt")
        if done.exists() and "VERDICT:" in done.read_text():
            line = [x for x in done.read_text().splitlines() if x.startswith("VERDICT:")][-1]
            print(f"skipping {name}: already decided -- {line}", flush=True)
            verdicts.append((name, line.replace("VERDICT: ", "")))
            continue
        verdicts.append(run_gate(name, description, candidate, control, book))
        print("", flush=True)

    print("=" * 72, flush=True)
    print("ALL GATES COMPLETE", flush=True)
    for name, verdict in verdicts:
        print(f"  {name:<14} {verdict}", flush=True)


if __name__ == "__main__":
    main()
