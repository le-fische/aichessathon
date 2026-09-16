"""Chart 4: round 103 -- the position where search depth could not out-run the evaluation.

FEN, moves, node counts and evaluations are taken from tools/probe/FINDINGS.md.
"""
from theme import *

FEN = "6k1/q7/P1p5/5p2/4nQp1/R2p2P1/1P6/7K w - - 0 59"
# Solid glyphs for both sides; colour, not glyph shape, carries the side, so the
# board reads correctly on a light or a dark surface.
GLYPH = {"k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟"}
PIECE_W, PIECE_B = "#f7f7f4", "#131315"

W, H = 1600, 1000
BX, BY, SQ = 96, 250, 82


def board_squares(fen):
    out = {}
    for r, row in enumerate(fen.split()[0].split("/")):
        f = 0
        for ch in row:
            if ch.isdigit():
                f += int(ch)
            else:
                out[(f, r)] = ch
                f += 1
    return out


def sq_xy(file_, rank_):          # rank_ 0 = rank 8 (top row)
    return BX + file_ * SQ, BY + rank_ * SQ


def build(mode):
    t = THEMES[mode]
    o = [svg_open(W, H, t), rect(48, 48, W - 96, H - 96, t["surface"], rx=10)]
    o.append(text(64, 112, "It found the win. It could not afford it.", t["ink"], 40, 600, spacing="-0.5"))
    o.append(text(64, 150, "Round 103 · a won endgame drawn · reproduced and diagnosed, not guessed",
                  t["secondary"], 19))

    pieces = board_squares(FEN)
    for r in range(8):
        for f in range(8):
            x, y = sq_xy(f, r)
            o.append(rect(x, y, SQ, SQ, t["sq_light"] if (f + r) % 2 == 0 else t["sq_dark"]))

    # Files and ranks
    for f in range(8):
        x, _ = sq_xy(f, 0)
        o.append(text(x + SQ / 2, BY + 8 * SQ + 26, "abcdefgh"[f], t["muted"], 14,
                      anchor="middle", family=MONO))
    for r in range(8):
        _, y = sq_xy(0, r)
        o.append(text(BX - 16, y + SQ / 2 + 5, str(8 - r), t["muted"], 14, anchor="end", family=MONO))

    # The two candidate moves, drawn before the pieces so glyphs stay on top.
    def centre(alg):
        f = "abcdefgh".index(alg[0]); r = 8 - int(alg[1])
        x, y = sq_xy(f, r); return x + SQ / 2, y + SQ / 2

    a3 = centre("a3"); d3 = centre("d3"); b3 = centre("b3")
    o.append(line(a3[0], a3[1], d3[0], d3[1], t["critical"], 5, cap="round", opacity=0.55))
    o.append(line(a3[0], a3[1] - 4, b3[0], b3[1] - 4, t["good"], 5, cap="round", opacity=0.75))
    o.append(rect(d3[0] - SQ / 2 + 3, d3[1] - SQ / 2 + 3, SQ - 6, SQ - 6, "none",
                  rx=4, stroke=t["critical"], sw=3))
    o.append(rect(b3[0] - SQ / 2 + 3, b3[1] - SQ / 2 + 3, SQ - 6, SQ - 6, "none",
                  rx=4, stroke=t["good"], sw=3))

    for (f, r), ch in pieces.items():
        x, y = sq_xy(f, r)
        white = ch.isupper()
        o.append(text(x + SQ / 2, y + SQ - 17, GLYPH[ch.lower()],
                      PIECE_W if white else PIECE_B, 54, anchor="middle", family=CHESS,
                      extra=f'stroke="{PIECE_B if white else PIECE_W}" stroke-width="1.6" '
                            f'paint-order="stroke" stroke-linejoin="round"'))

    o.append(text(BX, BY - 18, FEN, t["muted"], 14, family=MONO))

    # --- right-hand panel ---
    PX = 800
    o.append(text(PX, 292, "White to move. 26 seconds left.", t["ink"], 22, 600))
    o.append(text(PX, 322, "Not time trouble — the engine had four times the clock it needed.",
                  t["secondary"], 17))

    rows = [
        ("critical", "✗", "Rxd3", "played", "+219", "3,470,125", "1.1 s", "wins a pawn, throws the win"),
        ("good",     "✓", "Rb3",  "correct", "+313", "24,065,816", "7.5 s", "found only at 10× the clock"),
    ]
    for i, (key, icon, mv, tag, sc, nodes, secs, note) in enumerate(rows):
        y = 386 + i * 150
        col = t[key]
        o.append(rect(PX, y - 34, 656, 122, t["band"], rx=8))
        o.append(text(PX + 24, y, icon, col, 22, 700))
        o.append(text(PX + 58, y, mv, t["ink"], 26, 600, family=MONO))
        o.append(text(PX + 148, y, tag, col, 16, 600, spacing="0.6"))
        o.append(text(PX + 632, y, sc, t["ink"], 22, 600, anchor="end", family=MONO))
        o.append(text(PX + 24, y + 30, f"{nodes} nodes · {secs}", t["secondary"], 16, family=MONO))
        o.append(text(PX + 24, y + 58, note, t["muted"], 16))

    o.append(line(PX, 700, PX + 656, 700, t["grid"], 1))
    o.append(text(PX, 738, "Why", t["ink"], 20, 600))
    for i, s in enumerate([
        "static eval after Rb3      +108 cp",
        "static eval after Rxd3     +343 cp",
    ]):
        o.append(text(PX, 774 + i * 26, s, t["secondary"], 17, family=MONO))
    o.append(text(PX, 846,
                  "The search has to out-depth its own evaluation by 235 cp.",
                  t["ink"], 18, 500))
    o.append(text(PX, 872, "One second does not buy that. The search was never the problem —",
                  t["secondary"], 17))
    o.append(text(PX, 896, "the evaluation was wrong in exactly the position that decided the game.",
                  t["secondary"], 17))

    o.append(footer(W, H, t, "Three candidate fixes tried against it. All three left the move unchanged."))
    o.append("</svg>")
    return "".join(o)


for m in ("light", "dark"):
    open(f"out/04-round-103-{m}.svg", "w").write(build(m))
print("ok")
