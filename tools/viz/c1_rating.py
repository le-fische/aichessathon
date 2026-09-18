"""Chart 1: the rating trajectory across all 108 rated rounds.

Data: the dashboard's own rating history, R1..R108. Annotations are limited to
events with a written source in runs/ -- the moves-to-go regression window and
the round v11 went live -- plus the peak and final values.
"""
from theme import *

RATING = [1575,1626,1575,1582,1547,1549,1543,1505,1470,1438,1484,1513,1494,1493,
          1436,1489,1485,1566,1487,1455,1474,1438,1428,1391,1443,1487,1406,1377,
          1442,1496,1499,1536,1538,1501,1501,1499,1509,1486,1497,1500,1525,1529,
          1528,1516,1505,1489,1470,1466,1483,1484,1482,1498,1514,1501,1501,1520,
          1511,1529,1535,1531,1591,1635,1683,1636,1683,1723,1686,1660,1687,1706,
          1705,1728,1729,1714,1693,1709,1706,1687,1670,1654,1653,1673,1657,1658,
          1672,1685,1696,1713,1726,1716,1779,1835,1789,1830,1794,1753,1723,1697,
          1700,1730,1736,1742,1744,1743,1703,1739,1790,1749,1699]

W, H = 1600, 900
L, R, TOP, BOT = 96, 96, 210, 116
YMIN, YMAX = 1350, 1870


def build(mode):
    t = THEMES[mode]
    pw, ph = W - L - R, H - TOP - BOT

    def px(i):   return L + (i / (len(RATING) - 1)) * pw
    def py(v):   return TOP + (1 - (v - YMIN) / (YMAX - YMIN)) * ph

    o = [svg_open(W, H, t), rect(48, 48, W - 96, H - 96, t["surface"], rx=10)]

    # Header
    o.append(text(64, 112, "Nine days on the ladder", t["ink"], 40, 600, spacing="-0.5"))
    o.append(text(64, 150, "Self-written Python chess engine · AI Chessathon 2026 · 109 rated games",
                  t["secondary"], 19))

    # Gridlines and y labels
    for v in range(1400, 1851, 100):
        o.append(line(L, py(v), W - R, py(v), t["grid"], 1))
        o.append(text(L - 16, py(v) + 6, str(v), t["muted"], 15, anchor="end", family=MONO))

    # The documented regression window: platform v6's moves-to-go clock, rounds 19-25.
    o.append(rect(px(18), TOP, px(24) - px(18), ph, t["band"]))
    o.append(text((px(18) + px(24)) / 2, TOP + 30, "R19–25", t["muted"], 14,
                  anchor="middle", family=MONO))
    o.append(text((px(18) + px(24)) / 2, TOP + 52, "clock regression", t["muted"], 14, anchor="middle"))
    o.append(text((px(18) + px(24)) / 2, TOP + 72, "reverted", t["muted"], 14, anchor="middle"))

    # x ticks
    for r in (1, 20, 40, 60, 80, 109):
        o.append(text(px(r - 1), H - BOT + 34, f"R{r}", t["muted"], 15, anchor="middle", family=MONO))
    o.append(line(L, TOP + ph, W - R, TOP + ph, t["axis"], 1))

    # The series
    pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(RATING))
    o.append(f'<polyline points="{pts}" fill="none" stroke="{t["series1"]}" '
             f'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>')

    # v11 goes live at R91 -- the one version->round mapping with a written source.
    i91 = 90
    o.append(line(px(i91), py(RATING[i91]) + 14, px(i91), py(1622), t["axis"], 1, dash="3 4"))
    o.append(text(px(i91), py(1604), "v11 live · R91", t["secondary"], 15, anchor="middle", weight=500))

    # Peak and final, direct-labelled (never a label on every point).
    ipk = RATING.index(1835)
    o.append(circle(px(ipk), py(1835), 6, t["series1"], t["surface"], 2.5))
    o.append(text(px(ipk), py(1835) - 22, "peak 1835", t["ink"], 18, 600, anchor="middle"))

    ifn = len(RATING) - 1
    o.append(circle(px(ifn), py(RATING[ifn]), 6, t["series1"], t["surface"], 2.5))
    o.append(line(px(ifn), py(RATING[ifn]) + 14, px(ifn), py(1622), t["axis"], 1, dash="3 4"))
    o.append(text(px(ifn), py(1604), "final 1699", t["ink"], 18, 600, anchor="end"))
    o.append(text(px(ifn), py(1566), "#191 of 465", t["secondary"], 15, anchor="end"))

    o.append(circle(px(0), py(RATING[0]), 5, t["surface"], t["series1"], 2.5))
    o.append(text(px(0) + 14, py(RATING[0]) - 14, "start 1575", t["secondary"], 15))

    o.append(footer(W, H, t, "13 builds shipped · the ladder only seeded the draw; a 13-round Swiss decided the London seats"))
    o.append("</svg>")
    return "".join(o)


for m in ("light", "dark"):
    open(f"out/01-rating-trajectory-{m}.svg", "w").write(build(m))
print("ok")
