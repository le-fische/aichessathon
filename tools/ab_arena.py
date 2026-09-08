# ruff: noqa
"""Deterministic A/B arena for engine changes.

Plays build A against build B from a reproducible opening book, each position
twice with colours swapped, under a fixed node budget so that wall-clock jitter
cannot change the result. Byte-identical builds must score exactly 50.0%.

Usage:
    SEARCH_MAX_NODES is set by --nodes; do not set it yourself.

    # run the whole thing in one go
    uv run python tools/ab_arena.py --a . --b BASE --games 40 --nodes 40000 --out run.jsonl

    # or in chunks, when each shell has a short time limit; append to one file
    uv run python tools/ab_arena.py --a . --b BASE --games 40 --nodes 40000 \
        --out run.jsonl --start 0 --count 8
    ... repeat with --start 8, 16, 24, 32 ...
    uv run python tools/ab_arena.py --games 40 --out run.jsonl --summarize

Chunking is safe because the book is seeded and each game index maps to a fixed
(book position, colour) pair, so results are identical however you slice them.
Already-recorded game indices are skipped, making a re-run idempotent.

Why fixed nodes: on this hardware the completed depth of a time-limited search
varies between runs of the same binary, so a time-limited A/B measures the
scheduler as much as the change. Node-limited search is deterministic.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from pathlib import Path
from typing import TypedDict

# Run from anywhere: put the repository root (the parent of tools/) on the path
# so `harness` imports the same way `python -m harness.arena` does.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chess

from harness.referee import FAILED_TERMINATIONS, play_match
from harness.rules import PLY_CAP
from harness.sandbox import local


class GameRecord(TypedDict):
    """One finished game, as stored in the JSONL results file."""

    index: int
    book: int
    a_is_white: bool
    result: str
    termination: str


# Material values used only to reject lopsided book positions.
_BOOK_PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}


def _material_balance(board: chess.Board) -> int:
    """White pieces minus black pieces, in pawns."""
    return sum(
        value * (len(board.pieces(piece, chess.WHITE)) - len(board.pieces(piece, chess.BLACK)))
        for piece, value in _BOOK_PIECE_VALUES.items()
    )


def build_book(count: int, plies: int, seed: int) -> list[str]:
    """Return `count` distinct opening FENs produced by a seeded random walk.

    A position is accepted only when it is quiet enough to be a fair start:
    material is level, the side to move is not already in check, and the game
    is not over. The seed makes the book reproducible across runs and machines.
    """
    rng = random.Random(seed)
    book: list[str] = []
    seen: set[str] = set()
    attempts = 0
    max_attempts = count * 200
    while len(book) < count and attempts < max_attempts:
        attempts += 1
        board = chess.Board()
        for _ in range(plies):
            moves = list(board.legal_moves)
            if not moves:
                break
            board.push(rng.choice(moves))
        if board.is_game_over(claim_draw=True):
            continue
        if board.is_check():
            continue
        if _material_balance(board) != 0:
            continue
        fen = board.fen()
        if fen in seen:
            continue
        seen.add(fen)
        book.append(fen)
    if len(book) < count:
        raise SystemExit(f"could only build {len(book)} of {count} book positions; lower --games")
    return book


def _elo(score: float) -> float:
    """Elo difference implied by a score in (0, 1); clamped at the extremes."""
    if score <= 0.0:
        return -800.0
    if score >= 1.0:
        return 800.0
    return -400.0 * math.log10(1.0 / score - 1.0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fixed-node A/B between two engine builds.")
    parser.add_argument("--a", type=Path, default=Path("."), help="candidate build directory")
    parser.add_argument("--b", type=Path, required=True, help="baseline build directory")
    parser.add_argument("--games", type=int, default=40, help="total games; rounded up to even")
    parser.add_argument("--nodes", type=int, default=40_000, help="node budget per move, per side")
    parser.add_argument("--book-plies", type=int, default=8, help="random plies per book position")
    parser.add_argument(
        "--seed", type=int, default=20260905, help="book seed; keep fixed across A/Bs"
    )
    parser.add_argument(
        "--base-ms", type=int, default=600_000, help="clock; large so nodes bind, not time"
    )
    parser.add_argument("--increment-ms", type=int, default=0)
    parser.add_argument("--ply-cap", type=int, default=PLY_CAP)
    parser.add_argument("--out", type=Path, help="JSONL results file; enables resume")
    parser.add_argument("--start", type=int, default=0, help="first game index to play")
    parser.add_argument("--count", type=int, help="how many games to play this invocation")
    parser.add_argument(
        "--summarize", action="store_true", help="print the summary for --out and exit"
    )
    arguments = parser.parse_args()

    games = arguments.games + (arguments.games % 2)  # colour pairs must be complete
    pairs = games // 2
    book = build_book(pairs, arguments.book_plies, arguments.seed)

    # Load anything already recorded so a chunked run never repeats a game.
    recorded: dict[int, GameRecord] = {}
    if arguments.out and arguments.out.exists():
        for line in arguments.out.read_text().splitlines():
            if line.strip():
                entry: GameRecord = json.loads(line)
                recorded[entry["index"]] = entry

    a_dir = arguments.a.resolve()
    b_dir = arguments.b.resolve()

    if not arguments.summarize:
        # Both agent processes inherit this, so neither side gets a node advantage.
        os.environ["SEARCH_MAX_NODES"] = str(arguments.nodes)

        last = games if arguments.count is None else min(games, arguments.start + arguments.count)
        for index in range(arguments.start, last):
            if index in recorded:
                print(f"game {index + 1}/{games}: already recorded, skipping", flush=True)
                continue
            pair, colour_slot = divmod(index, 2)
            a_is_white = colour_slot == 0
            start_fen = book[pair]
            white, black = (a_dir, b_dir) if a_is_white else (b_dir, a_dir)
            outcome = play_match(
                local(white),
                local(black),
                arguments.base_ms,
                arguments.increment_ms,
                ply_cap=arguments.ply_cap,
                start_fen=start_fen,
            )
            record: GameRecord = {
                "index": index,
                "book": pair,
                "a_is_white": a_is_white,
                "result": outcome.result,
                "termination": outcome.termination,
            }
            recorded[index] = record
            if arguments.out:
                with arguments.out.open("a") as handle:
                    handle.write(json.dumps(record) + "\n")
            print(
                f"game {index + 1}/{games} (book {pair + 1}, A as "
                f"{'white' if a_is_white else 'black'}): "
                f"{outcome.result} by {outcome.termination}",
                flush=True,
            )

    # Summarise every game recorded so far, not just this invocation's chunk.
    wins = draws = losses = 0
    terminations: dict[str, int] = {}
    for entry in recorded.values():
        terminations[entry["termination"]] = terminations.get(entry["termination"], 0) + 1
        if entry["result"] in ("draw", "void"):
            draws += 1
        elif (entry["result"] == "white") == entry["a_is_white"]:
            wins += 1
        else:
            losses += 1

    played = wins + draws + losses
    if played == 0:
        raise SystemExit("no games recorded")
    games = played
    score = (wins + draws / 2) / games
    # Standard error of the mean score, treating a draw as half a point.
    variance = (wins * (1 - score) ** 2 + draws * (0.5 - score) ** 2 + losses * score**2) / games
    stderr = math.sqrt(variance / games) if games else 0.0

    print(f"\nA = {a_dir}")
    print(f"B = {b_dir}")
    print(f"book seed {arguments.seed}, {arguments.book_plies} plies, {pairs} positions")
    print(f"nodes/move {arguments.nodes}")
    print(f"games recorded {games} of {pairs * 2}")
    print(f"+{wins} ={draws} -{losses} over {games} games")
    print(f"A score {score:.1%} +/- {stderr:.1%} (1 sigma)")
    print(f"implied Elo {_elo(score):+.0f} [{_elo(max(0.0, score - 2 * stderr)):+.0f}, "
          f"{_elo(min(1.0, score + 2 * stderr)):+.0f}] (95%)")
    summary = ", ".join(f"{name} {count}" for name, count in sorted(terminations.items()))
    print("terminations: " + summary)

    broken = {name: count for name, count in terminations.items() if name in FAILED_TERMINATIONS}
    if broken:
        raise SystemExit(
            "a build failed to finish a game: "
            + ", ".join(f"{name} {count}" for name, count in broken.items())
        )


if __name__ == "__main__":
    main()
