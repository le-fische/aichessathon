"""Chart 3: engine architecture -- the two search paths and the invariant between them."""
from theme import *

W, H = 1600, 1010


def box(x, y, w, h, t, fill, stroke, dash=None):
    return rect(x, y, w, h, fill, rx=8, stroke=stroke, sw=1.5, dash=dash)


def arrow(x1, y1, x2, y2, col, dash=None):
    head = (f'<path d="M {x2:.1f} {y2:.1f} l -5 -9 l 10 0 z" fill="{col}"/>')
    return line(x1, y1, x2, y2 - 8, col, 1.5, dash=dash) + head


def build(mode):
    t = THEMES[mode]
    o = [svg_open(W, H, t), rect(48, 48, W - 96, H - 96, t["surface"], rx=10)]
    o.append(text(64, 112, "Two search paths, one evaluation contract", t["ink"], 40, 600, spacing="-0.5"))
    o.append(text(64, 150, "Engine architecture · written from scratch in Python, no third-party engine code",
                  t["secondary"], 19))

    # Platform
    o.append(box(600, 190, 400, 76, t, t["band"], t["axis"]))
    o.append(text(800, 220, "competition platform", t["secondary"], 17, anchor="middle"))
    o.append(text(800, 247, "get_move(fen, time_left_ms) → uci", t["muted"], 15,
                  anchor="middle", family=MONO))
    o.append(arrow(800, 266, 800, 296, t["axis"]))

    # agent.py
    o.append(box(600, 296, 400, 74, t, t["surface"], t["ink"]))
    o.append(text(800, 328, "agent.py", t["ink"], 22, 600, anchor="middle", family=MONO))
    o.append(text(800, 353, "try numba · fall back on any exception", t["muted"], 15, anchor="middle"))

    o.append(arrow(760, 370, 420, 452, t["series1"]))
    o.append(arrow(840, 370, 1180, 452, t["muted"], dash="4 5"))
    o.append(text(548, 398, "primary", t["series1"], 15, 600, anchor="middle"))
    o.append(text(1056, 398, "fallback", t["muted"], 15, 600, anchor="middle"))

    # --- numba column ---
    o.append(box(140, 452, 560, 300, t, t["surface"], t["series1"]))
    o.append(text(168, 490, "nsearch.py", t["series1"], 22, 600, family=MONO))
    o.append(text(168, 516, "numba-JIT · this is what plays", t["muted"], 15))
    o.append(line(168, 534, 672, 534, t["grid"], 1))

    feats = ["negamax + alpha–beta, iterative deepening",
             "transposition table, aspiration windows",
             "MVV-LVA + killer + history ordering",
             "quiescence, null-move pruning, LMR",
             "check extensions, SEE capture pruning"]
    for i, f in enumerate(feats):
        o.append(circle(176, 560 + i * 26, 2.5, t["series1"]))
        o.append(text(192, 565 + i * 26, f, t["secondary"], 16))

    o.append(text(168, 712, "2.7 M", t["ink"], 30, 600, family=MONO))
    o.append(text(168, 734, "nodes / sec", t["muted"], 14))
    o.append(text(370, 712, "12.4", t["ink"], 30, 600, family=MONO))
    o.append(text(370, 734, "plies at 120 s + 0.5 s", t["muted"], 14))

    # --- python column ---
    o.append(box(900, 452, 560, 300, t, t["surface"], t["axis"], dash="5 5"))
    o.append(text(928, 490, "search.py", t["secondary"], 22, 600, family=MONO))
    o.append(text(928, 516, "pure Python · safety net and reference", t["muted"], 15))
    o.append(line(928, 534, 1432, 534, t["grid"], 1))
    for i, f in enumerate(["same algorithm, no JIT",
                           "runs if numba is absent or raises",
                           "the readable definition of correct",
                           "cross-checked against the numba path",
                           "never flagged a game in production"]):
        o.append(circle(936, 560 + i * 26, 2.5, t["muted"]))
        o.append(text(952, 565 + i * 26, f, t["secondary"], 16))

    o.append(text(928, 712, "58 k", t["secondary"], 30, 600, family=MONO))
    o.append(text(928, 734, "nodes / sec", t["muted"], 14))
    o.append(text(1130, 712, "6", t["secondary"], 30, 600, family=MONO))
    o.append(text(1130, 734, "plies at the same clock", t["muted"], 14))

    # --- the invariant ---
    o.append(arrow(420, 752, 420, 812, t["series1"]))
    o.append(arrow(1180, 752, 1180, 812, t["axis"], dash="4 5"))
    o.append(box(140, 812, 1320, 106, t, t["band"], t["series3"]))
    o.append(text(176, 848, "bitboard.evaluate()", t["ink"], 19, 600, family=MONO))
    o.append(text(1424, 848, "evaluation.evaluate()", t["ink"], 19, 600, anchor="end", family=MONO))
    o.append(text(800, 845, "must agree exactly", t["series3"], 19, 600, anchor="middle"))
    o.append(line(420, 862, 700, 862, t["series3"], 1.5))
    o.append(line(900, 862, 1180, 862, t["series3"], 1.5))
    o.append(text(800, 884, "verified by random walk over 7,663 positions · caught two real divergences",
                  t["secondary"], 16, anchor="middle"))

    o.append(footer(W, H, t, "Tapered PeSTO evaluation · Syzygy tablebases to 4 pieces · Python 3.12 + numba"))
    o.append("</svg>")
    return "".join(o)


for m in ("light", "dark"):
    open(f"out/03-architecture-{m}.svg", "w").write(build(m))
print("ok")
