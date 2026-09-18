"""Chart 5: the 13-round qualification Swiss -- the event that actually decided seats.

Field, points and the cut are read from the official final-qualification table:
334 ranked entries, 50 London seats.
"""
from theme import *

# points -> number of entrants, from the final qualification leaderboard
DIST = {0.5: 1, 1.0: 0, 1.5: 1, 2.0: 1, 2.5: 0, 3.0: 2, 3.5: 6, 4.0: 19, 4.5: 22,
        5.0: 28, 5.5: 31, 6.0: 39, 6.5: 33, 7.0: 41, 7.5: 28, 8.0: 29, 8.5: 22,
        9.0: 16, 9.5: 9, 10.0: 5, 10.5: 1}
OURS, CUT, FIELD, SEATS = 7.0, 8.5, 334, 50

W, H = 1600, 900
L, R, TOP = 96, 96, 300
PH = 380


def build(mode):
    t = THEMES[mode]
    keys = sorted(DIST)
    pw = W - L - R
    step = pw / len(keys)
    bw = step * 0.62
    mx = max(DIST.values())

    def bx(i):  return L + i * step + (step - bw) / 2
    def by(n):  return TOP + PH - (n / mx) * PH

    o = [svg_open(W, H, t), rect(48, 48, W - 96, H - 96, t["surface"], rx=10)]
    o.append(text(64, 112, "Missed London by a point and a half", t["ink"], 40, 600, spacing="-0.5"))
    o.append(text(64, 150, "Final qualification Swiss · 13 rounds · 334 ranked entries · top 50 took a seat",
                  t["secondary"], 19))

    # headline figures
    for i, (v, lab) in enumerate([("#135", "final placing"), ("7.0", "points from 13"),
                                  ("5–4–4", "win–draw–loss"), ("1785", "performance rating")]):
        x = 64 + i * 200
        o.append(text(x, 216, v, t["ink"], 34, 600, family=MONO))
        o.append(text(x, 240, lab, t["muted"], 15))

    cut_i = keys.index(CUT)
    # everything at or above the cut is the qualifying side of the draw
    o.append(rect(L + cut_i * step, TOP - 34, pw - cut_i * step, PH + 34, t["band"]))

    for i, k in enumerate(keys):
        n = DIST[k]
        if n == 0:
            continue
        ours = abs(k - OURS) < 1e-9
        col = t["series1"] if ours else t["axis"]
        o.append(rect(bx(i), by(n), bw, TOP + PH - by(n), col, rx=4))
        if n >= 30 and not ours:
            o.append(text(bx(i) + bw / 2, by(n) - 10, str(n), t["muted"], 15,
                          anchor="middle", family=MONO))

    # axis
    o.append(line(L, TOP + PH, W - R, TOP + PH, t["axis"], 1))
    for i, k in enumerate(keys):
        if k * 2 % 2 == 0:
            o.append(text(bx(i) + bw / 2, TOP + PH + 28, f"{k:g}", t["muted"], 15,
                          anchor="middle", family=MONO))
    o.append(text((L + W - R) / 2, TOP + PH + 62, "points from 13 games", t["secondary"], 16, anchor="middle"))

    # the cut
    cx = L + cut_i * step
    o.append(line(cx, TOP - 34, cx, TOP + PH, t["ink"], 1.5, dash="4 5"))
    o.append(text(W - R, TOP - 44, f"{SEATS} London seats — cut at {CUT:g}, split on Buchholz",
                  t["ink"], 16, 600, anchor="end"))

    # ours
    ox = bx(keys.index(OURS)) + bw / 2
    o.append(line(ox, by(DIST[OURS]) - 34, ox, by(DIST[OURS]) - 14, t["series1"], 1.5))
    o.append(text(ox, by(DIST[OURS]) - 42, "us — 7.0, the modal score (41)", t["series1"], 16, 600, anchor="middle"))

    o.append(text(64, H - 118, "Three more draws would have reached the cut. The engine that played this was "
                              "shipped seven minutes before the lock", t["secondary"], 17))
    o.append(text(64, H - 94, "and had never played a rated game.", t["secondary"], 17))

    o.append(footer(W, H, t, "Ladder rank #191 of 465 seeded the draw; it did not decide seats"))
    o.append("</svg>")
    return "".join(o)


for m in ("light", "dark"):
    open(f"out/05-final-swiss-{m}.svg", "w").write(build(m))
print("ok")
