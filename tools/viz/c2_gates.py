"""Chart 2: the seven gates as score +/- 1 standard error against the 50% line.

Every figure is taken verbatim from the results file named beside it in runs/.
"""
from theme import *

# (label, detail, score%, sigma%, games, verdict, source)
GATES = [
    ("King shelter",            "shelter term in both evaluations", 56.7, 4.9, 60, "ship",
     "runs/2026-09-10-king-safety"),
    ("Contempt",                "score a draw at −25 cp",      52.5, 4.5, 60, "unmeasured",
     "runs/2026-09-10-contempt"),
    ("Clock 0.045 → 0.050", "spend more of the budget",        51.7, 6.0, 30, "unmeasured",
     "runs/2026-09-10-clock50"),
    ("v13 candidate",           "clock + contempt together",        51.2, 5.7, 40, "unmeasured",
     "runs/2026-09-11-v13"),
    ("Pawn structure",          "open file, doubled, isolated",     40.0, 6.4, 30, "revert",
     "runs/2026-09-10-terms34"),
    ("NNUE evaluation",         "768→256→1, 2M positions", 1.7, 1.7, 60, "revert",
     "runs/2026-09-09-nnue"),
]

STYLE = {
    "ship":       ("good",     "✓", "SHIPPED"),
    "unmeasured": ("warning",  "–", "UNMEASURED"),
    "revert":     ("critical", "✗", "REVERTED"),
}

W, H = 1600, 900
L, TOP = 430, 268
XMIN, XMAX = -3.0, 66.0
PW = 860


def build(mode):
    t = THEMES[mode]

    def px(v): return L + (v - XMIN) / (XMAX - XMIN) * PW

    o = [svg_open(W, H, t), rect(48, 48, W - 96, H - 96, t["surface"], rx=10)]
    o.append(text(64, 112, "One change in six cleared its gate", t["ink"], 40, 600, spacing="-0.5"))
    o.append(text(64, 150,
                  "Every candidate change played 30–60 games at the tournament clock against a frozen",
                  t["secondary"], 19))
    o.append(text(64, 178,
                  "snapshot, colours swapped. If the ±1σ interval crosses 50%, the change is unmeasured — not neutral.",
                  t["secondary"], 19))

    # 50% reference
    o.append(line(px(50), TOP - 42, px(50), TOP + len(GATES) * 88 - 24, t["axis"], 1.5, dash="4 5"))
    o.append(text(px(50), TOP - 54, "50% — no effect", t["secondary"], 15, anchor="middle", weight=500))

    for k, v in enumerate((0, 25, 50)):
        o.append(text(px(v), TOP + len(GATES) * 88 + 16, f"{v}%", t["muted"], 15,
                      anchor="middle", family=MONO))

    for i, (name, detail, score, sig, games, verdict, src) in enumerate(GATES):
        y = TOP + i * 88
        key, icon, word = STYLE[verdict]
        col = t[key]

        o.append(text(64, y + 1, name, t["ink"], 21, 600))
        o.append(text(64, y + 26, detail, t["muted"], 15))
        o.append(text(L - 40, y + 1, f"{games} games", t["muted"], 15, anchor="end", family=MONO))

        lo, hi = max(score - sig, XMIN), score + sig
        o.append(line(px(lo), y - 5, px(hi), y - 5, col, 2.5, cap="round"))
        for e in (lo, hi):
            o.append(line(px(e), y - 13, px(e), y + 3, col, 2.5, cap="round"))
        o.append(circle(px(score), y - 5, 7, col, t["surface"], 2.5))

        o.append(text(px(hi) + 22, y + 1, f"{score:.1f}% ± {sig:.1f}%", t["ink"], 18, 500, family=MONO))

        # Status never travels on colour alone: icon + word, both present.
        o.append(text(W - 64, y - 4, icon, col, 20, 700, anchor="end"))
        o.append(text(W - 92, y - 4, word, col, 15, 600, anchor="end", spacing="0.6"))
        o.append(text(W - 64, y + 26, src, t["muted"], 13, anchor="end", family=MONO))

    o.append(footer(W, H, t,
                    "A 60-game gate resolves about ±35 Elo. Most real evaluation terms are worth 5–20."))
    o.append("</svg>")
    return "".join(o)


for m in ("light", "dark"):
    open(f"out/02-gate-results-{m}.svg", "w").write(build(m))
print("ok")
