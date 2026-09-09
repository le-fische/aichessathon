"""Adversarial position suite for the AI Chessathon agent.

Every entry is a position that has historically broken a move generator, a
move encoder, or a clock policy. The point is not to check that the engine
plays well. The point is to check that it returns a legal, well-formed UCI
move at all, because per the rules an illegal or malformed move is an
instant loss and a crash is an instant loss.

Each case carries the time_left_ms the harness should hand it, because
several of these are only dangerous when the clock is nearly gone.

Run this file directly to self-validate the suite.
"""

from dataclasses import dataclass, field
from typing import Optional

import chess

MATCH_START_MS = 120_000  # 120s per side, per the docs
INCREMENT_MS = 500  # 0.5s per move


@dataclass
class Case:
    id: str
    fen: str
    category: str
    why: str
    time_left_ms: int = MATCH_START_MS
    # Moves that MUST NOT be legal in this position. Checked at suite
    # validation time against python-chess, and again against whatever the
    # engine returns. These are the outright rules violations.
    illegal_moves: Optional[list] = None
    # The harness asserts the engine returns one of these.
    must_choose: Optional[list] = None
    # Legal moves the engine must not select. Not a rules violation, just a
    # blunder bad enough to be worth failing the suite over.
    must_not_choose: Optional[list] = None
    # Expected number of legal moves, asserted at suite-validation time so a
    # typo'd FEN cannot silently weaken the suite.
    expect_legal_count: Optional[int] = None
    tags: list = field(default_factory=list)


CASES = [
    # ------------------------------------------------------------------
    # Move generation: the classic traps
    # ------------------------------------------------------------------
    Case(
        id="ep_horizontal_pin",
        fen="8/8/8/8/k2Pp2Q/8/8/3K4 b - d3 0 1",
        category="movegen",
        why=(
            "En passant capture d4 would remove two pawns from the rank and "
            "expose the black king to Qh4. The single most common legality "
            "bug in hand-rolled move generators."
        ),
        illegal_moves=["e4d3"],
        expect_legal_count=6,
        tags=["legality", "en-passant"],
    ),
    Case(
        id="ep_available_and_legal",
        fen="rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3",
        category="movegen",
        why="En passant is genuinely available. A generator that drops e.p. entirely still passes the pin test above, so we need the positive case too.",
        expect_legal_count=31,
        tags=["en-passant"],
    ),
    Case(
        id="ep_pinned_pawn_diagonal",
        fen="8/8/8/2k5/3Pp3/8/8/4K1R1 b - d3 0 1",
        category="movegen",
        why="En passant with a rook on the e-file behind the capturing pawn. Tests that the pin check considers the departing square, not just the arrival square.",
        tags=["legality", "en-passant"],
    ),
    Case(
        id="castle_through_check",
        fen="r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
        category="movegen",
        why="All four castles available. Baseline for the castling encoder.",
        expect_legal_count=26,
        tags=["castling"],
    ),
    Case(
        id="castle_blocked_by_attack",
        fen="r3k2r/8/8/8/8/8/6b1/R3K2R w KQkq - 0 1",
        category="movegen",
        why=(
            "Bg2 attacks f1, so O-O is illegal but O-O-O is legal. A generator "
            "that only checks the king's origin and destination squares, and "
            "not the square it transits, emits an illegal castle here."
        ),
        illegal_moves=["e1g1"],
        tags=["legality", "castling"],
    ),
    Case(
        id="castle_uci_encoding",
        fen="4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1",
        category="protocol",
        why=(
            "Castling must serialise as e1g1 / e1c1. If the board was built "
            "with chess960=True anywhere in the pipeline, python-chess emits "
            "e1h1 / e1a1 in Shredder notation and the runner scores it illegal. "
            "This is a silent, total game loss and it looks fine in a PGN."
        ),
        illegal_moves=["e1h1", "e1a1"],
        tags=["encoding", "castling"],
    ),
    Case(
        id="promotion_forced",
        fen="8/P7/8/8/8/7k/6r1/7K w - - 0 1",
        category="protocol",
        why=(
            "The white king is stalemated by Rg2 and Kh3, so every legal move "
            "in the position is a promotion. There is no way to sidestep this "
            "case with a king move. A move encoder that omits the promotion "
            "suffix returns 'a7a8', which is malformed, and malformed loses "
            "the game on the spot."
        ),
        must_choose=["a7a8q", "a7a8r", "a7a8b", "a7a8n"],
        expect_legal_count=4,
        tags=["encoding", "promotion"],
    ),
    Case(
        id="promotion_with_capture",
        fen="1n2k3/P7/8/8/8/8/8/4K3 w - - 0 1",
        category="protocol",
        why="Capture-promotion (axb8=Q). Separate code path from a quiet promotion in most generators.",
        tags=["encoding", "promotion"],
    ),
    Case(
        id="underpromotion_to_avoid_stalemate",
        fen="8/6P1/8/8/8/8/8/k1K5 w - - 0 1",
        category="eval",
        why=(
            "g8=Q is stalemate and throws away a won game. g8=R keeps the win. "
            "Not a legality bug, but a search that never generates "
            "underpromotions cannot see the difference, and this is the single "
            "cheapest half point in any pawn endgame."
        ),
        must_not_choose=["g7g8q"],
        tags=["promotion", "search-quality"],
    ),
    Case(
        id="max_legal_moves_218",
        fen="R6R/3Q4/1Q4Q1/4Q3/2Q4Q/Q4Q2/pp1Q4/kBNN1KB1 w - - 0 1",
        category="movegen",
        why=(
            "218 legal moves, the theoretical maximum. Smokes out fixed-size "
            "move list buffers and any assumption that a movelist fits in a "
            "small array. Also a worst case for move ordering cost."
        ),
        expect_legal_count=218,
        tags=["capacity"],
    ),
    Case(
        id="kiwipete",
        fen="r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
        category="movegen",
        why="The standard perft position 2. Dense with pins, castles and captures. If perft is wrong anywhere it is usually wrong here.",
        expect_legal_count=48,
        tags=["perft"],
    ),
    Case(
        id="perft_position_3",
        fen="8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
        category="movegen",
        why="Standard perft position 3. Sparse, but rich in discovered checks and en passant edge cases.",
        expect_legal_count=14,
        tags=["perft"],
    ),
    Case(
        id="perft_position_4",
        fen="r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
        category="movegen",
        why="Standard perft position 4. Promotions, castling rights on one side only, and a pinned queen.",
        expect_legal_count=6,
        tags=["perft"],
    ),
    Case(
        id="perft_position_5",
        fen="rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
        category="movegen",
        why="Standard perft position 5. Known to break generators that mishandle promotion while in check.",
        expect_legal_count=44,
        tags=["perft"],
    ),

    # ------------------------------------------------------------------
    # Terminal and near-terminal positions
    # ------------------------------------------------------------------
    Case(
        id="single_legal_move",
        fen="7k/8/8/8/8/8/5Q2/6RK b - - 0 1",
        category="movegen",
        why="Exactly one legal move. Any search that returns an empty PV must still emit that move rather than None.",
        expect_legal_count=1,
        tags=["degenerate"],
    ),
    Case(
        id="single_evasion_by_capture",
        fen="1Q1k4/8/4K1p1/1r6/5p2/8/8/8 b - - 0 1",
        category="movegen",
        why=(
            "Black is in check and the only legal move in the position is "
            "Rxb8, a capture of the checking piece. Not a king move. A "
            "generator that handles check by enumerating king escapes first "
            "and short-circuiting will report no legal moves and crash."
        ),
        must_choose=["b5b8"],
        expect_legal_count=1,
        tags=["legality", "degenerate"],
    ),
    Case(
        id="double_check_king_must_move",
        fen="8/8/2r5/8/1k6/2B5/1R6/5K2 b - - 0 1",
        category="movegen",
        why=(
            "Double check from Bc3 and Rb2. In double check, blocking and "
            "capturing are both illegal no matter how attractive, and only "
            "king moves are legal. Generators that build evasions as "
            "'capture the checker, block the ray, or move the king' emit an "
            "illegal move here unless they special-case the double."
        ),
        illegal_moves=["c6c3", "b4b2"],
        expect_legal_count=5,
        tags=["legality", "degenerate"],
    ),
    Case(
        id="stalemate_no_legal_moves",
        fen="7k/5Q2/6K1/8/8/8/8/8 b - - 0 1",
        category="robustness",
        why=(
            "Zero legal moves. The runner should never ask for a move here, "
            "but if it does, or if this position turns up inside a self-play "
            "harness, the agent must not raise. An uncaught exception is a "
            "crash, and a crash is a loss."
        ),
        expect_legal_count=0,
        tags=["degenerate", "must-not-crash"],
    ),
    # ------------------------------------------------------------------
    # Clock policy: the cases clocksim.py never reaches
    # ------------------------------------------------------------------
    Case(
        id="clock_move_150",
        fen="8/5k2/8/3p4/3P4/8/5K2/8 w - - 40 150",
        category="clock",
        why=(
            "Move 150 with a high halfmove clock. clocksim.py stops at 84 "
            "plies, so nothing in the repo has ever exercised the clock policy "
            "this deep. Both previous clock failures only showed up in long games."
        ),
        time_left_ms=18_000,
        tags=["long-game"],
    ),
    Case(
        id="clock_move_250",
        fen="8/8/4k3/8/8/3K4/8/6R1 w - - 12 250",
        category="clock",
        why="Move 250, deep into the territory the 600-ply draw rule allows and nothing has tested.",
        time_left_ms=9_000,
        tags=["long-game"],
    ),
    Case(
        id="clock_near_ply_cap",
        fen="8/8/4k3/8/8/3K4/8/6R1 w - - 80 295",
        category="clock",
        why=(
            "Approaching the 600-ply cap where the game is drawn anyway. A "
            "time policy that divides remaining time by an estimate of moves "
            "left can allocate absurd amounts here, or divide by zero."
        ),
        time_left_ms=4_000,
        tags=["long-game"],
    ),
    Case(
        id="clock_almost_flagged",
        fen="r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 4 4",
        category="clock",
        why=(
            "300ms left, less than one increment. The engine must return "
            "something instantly. Overshooting here is a flag, and a flag is a loss."
        ),
        time_left_ms=300,
        tags=["panic"],
    ),
    Case(
        id="clock_one_ms",
        fen="r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 4 4",
        category="clock",
        why="1ms left. Pathological, but the runner can hand this over and a search that does not check the clock before its first iteration will flag.",
        time_left_ms=1,
        tags=["panic"],
    ),
    Case(
        id="clock_zero_ms",
        fen="r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 4 4",
        category="clock",
        why="Zero. Tests for division by zero in the time manager and for any negative-budget arithmetic.",
        time_left_ms=0,
        tags=["panic", "must-not-crash"],
    ),
    Case(
        id="clock_first_move_full",
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        category="clock",
        why=(
            "Standard start position at a full clock. Note the rated games do "
            "NOT start here, they start from a curated near-level position, so "
            "this is a control case rather than a realistic one."
        ),
        tags=["control"],
    ),

    # ------------------------------------------------------------------
    # Robustness against odd but legal inputs
    # ------------------------------------------------------------------
    Case(
        id="no_castling_rights",
        fen="r3k2r/8/8/8/8/8/8/R3K2R w - - 0 1",
        category="robustness",
        why="Rooks and kings on their home squares with every castling right gone. A generator that infers rights from piece placement emits an illegal castle.",
        illegal_moves=["e1g1", "e1c1"],
        tags=["legality", "castling"],
    ),
    Case(
        id="stale_ep_square",
        fen="rnbqkbnr/ppp1pppp/8/3p4/8/8/PPPPPPPP/RNBQKBNR w KQkq d6 0 2",
        category="robustness",
        why="An e.p. square is set but no pawn can actually capture there. Tests that the generator does not invent a capture from the FEN field alone.",
        tags=["en-passant"],
    ),
    Case(
        id="fifty_move_boundary",
        fen="8/8/4k3/8/8/3K4/8/6R1 w - - 99 120",
        category="robustness",
        why="Halfmove clock at 99. The next quiet move triggers the fifty-move draw, which the runner claims automatically. The engine should know it is about to draw.",
        time_left_ms=30_000,
        tags=["draw-rules"],
    ),
    Case(
        id="lone_kings_drawn",
        fen="8/8/4k3/8/8/3K4/8/8 w - - 0 60",
        category="robustness",
        why="Dead drawn, insufficient material. Some evaluators divide by material and produce NaN or an infinity here, which then poisons move selection.",
        tags=["degenerate"],
    ),
    Case(
        id="four_man_endgame_krk",
        fen="8/8/8/4k3/8/8/8/R3K3 w - - 0 1",
        category="tablebase",
        why=(
            "KRvK, three men. Relevant to the tablebase question: 5-man Syzygy "
            "is 378 MiB for WDL alone against a 50 MB submission budget, so it "
            "cannot ship. The 3-4 man set can. This is where that would pay off."
        ),
        tags=["endgame"],
    ),
    Case(
        id="four_man_kpkp",
        fen="8/5p2/8/4k3/8/2K5/3P4/8 w - - 0 1",
        category="tablebase",
        why="KPvKP, four men. Notoriously hard for a shallow search and exactly what a 4-man tablebase would resolve instantly.",
        tags=["endgame"],
    ),
]


def _build_generated_cases():
    """Cases easier to state as code than as a literal FEN."""
    extra = []

    # A genuine checkmate: black to move, no legal moves, king attacked.
    board = chess.Board()
    for san in ["f3", "e5", "g4", "Qh4"]:
        board.push_san(san)
    assert board.is_checkmate(), "fool's mate construction drifted"
    extra.append(
        Case(
            id="checkmate_delivered",
            fen=board.fen(),
            category="robustness",
            why=(
                "Fool's mate. Zero legal moves and the side to move is in "
                "check. Must not raise if the agent is ever handed it."
            ),
            expect_legal_count=0,
            tags=["degenerate", "must-not-crash"],
        )
    )
    return extra


def all_cases():
    cases = list(CASES)
    cases.extend(_build_generated_cases())
    return cases


def validate():
    """Assert every FEN parses and matches its declared expectations."""
    problems = []
    seen = set()
    for case in all_cases():
        if case.id in seen:
            problems.append(f"{case.id}: duplicate id")
        seen.add(case.id)

        try:
            board = chess.Board(case.fen)
        except ValueError as exc:
            problems.append(f"{case.id}: FEN does not parse: {exc}")
            continue

        if not board.is_valid():
            problems.append(f"{case.id}: FEN parses but board is not valid: {board.status()!r}")

        legal = {m.uci() for m in board.legal_moves}

        if case.expect_legal_count is not None and len(legal) != case.expect_legal_count:
            problems.append(
                f"{case.id}: expected {case.expect_legal_count} legal moves, board has {len(legal)}"
            )

        if case.must_choose:
            missing = [m for m in case.must_choose if m not in legal]
            if len(missing) == len(case.must_choose):
                problems.append(
                    f"{case.id}: none of must_choose {case.must_choose} are legal, "
                    "so the case can never pass"
                )

        if case.illegal_moves:
            wrongly_legal = [m for m in case.illegal_moves if m in legal]
            if wrongly_legal:
                problems.append(
                    f"{case.id}: moves declared illegal are actually legal: {wrongly_legal}"
                )

        if case.must_not_choose:
            not_legal = [m for m in case.must_not_choose if m not in legal]
            if not_legal:
                problems.append(
                    f"{case.id}: must_not_choose lists moves that are not legal "
                    f"anyway, so the assertion is vacuous: {not_legal}"
                )

        if case.time_left_ms < 0:
            problems.append(f"{case.id}: negative time_left_ms")

    return problems


if __name__ == "__main__":
    import sys

    issues = validate()
    cases = all_cases()
    if issues:
        print(f"SUITE INVALID: {len(issues)} problem(s)")
        for line in issues:
            print("  -", line)
        sys.exit(1)

    print(f"suite ok: {len(cases)} cases")
    by_cat = {}
    for c in cases:
        by_cat.setdefault(c.category, []).append(c.id)
    for cat in sorted(by_cat):
        print(f"  {cat:<12} {len(by_cat[cat]):>2}  {', '.join(sorted(by_cat[cat]))}")
