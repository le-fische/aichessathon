"""What does one cherry-picked 5-man endgame really cost in the 50 MB cap?

python-chess: "probing requires tablebase files for the specific material
composition, **as well as** material compositions transitively reachable by
captures and promotions." So a 5-man class is never a single file. This walks
that closure and totals the bytes, WDL-only and WDL+DTZ, against the real
per-file sizes from lichess's bytes.tsv.

Usage:
    BYTES_TSV=~/…/tb-scratch/bytes.tsv python tools/tb_closure_cost.py KRPvKR KBPvKB
    python tools/tb_closure_cost.py --all-5man     # rank every 5-man class
"""

import os
import sys

BYTES_TSV = os.path.expanduser(
    os.environ.get("BYTES_TSV", "~/Desktop/AIChessHackathon/tb-scratch/bytes.tsv")
)
ORDER = "KQRBNP"
PROMO = "QRBN"


def load_sizes():
    w, z = {}, {}
    for line in open(BYTES_TSV):
        if not line.strip():
            continue
        n, name = line.rstrip("\n").split("\t")
        stem, ext = name.rsplit(".", 1)
        (w if ext == "rtbw" else z)[stem] = int(n)
    return w, z


def canonical(white, black, known):
    """Syzygy orders the two sides by strength, not alphabetically, so try both
    and keep whichever the real file list knows."""
    a = "".join(sorted(white, key=ORDER.index))
    b = "".join(sorted(black, key=ORDER.index))
    for x, y in ((a, b), (b, a)):
        if f"{x}v{y}" in known:
            return f"{x}v{y}"
    return f"{a}v{b}" if (len(a), a) >= (len(b), b) else f"{b}v{a}"


def split(name):
    a, b = name.split("v")
    return list(a), list(b)


def closure(name, known):
    """Every class reachable by captures and by promotions, down to 3 men."""
    seen = set()
    stack = [name]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        white, black = split(cur)
        if len(white) + len(black) <= 3:
            continue
        # captures: remove any non-king piece from either side
        for side, other, flip in ((white, black, False), (black, white, True)):
            for i, pc in enumerate(side):
                if pc == "K":
                    continue
                rest = side[:i] + side[i + 1:]
                nxt = canonical(other, rest, known) if flip else canonical(rest, other, known)
                stack.append(nxt)
        # promotions: a pawn becomes Q/R/B/N
        for side, other, flip in ((white, black, False), (black, white, True)):
            if "P" not in side:
                continue
            i = side.index("P")
            for promo in PROMO:
                rest = side[:i] + [promo] + side[i + 1:]
                nxt = canonical(other, rest, known) if flip else canonical(rest, other, known)
                stack.append(nxt)
    return seen


def report(names, wsz, zsz, shipped):
    known = set(wsz)
    print(f"{'class':<10}{'files':>7}{'new files':>11}{'WDL new B':>14}{'+DTZ new B':>14}{'total new':>13}")
    rows = []
    for name in names:
        cl = closure(name, known)
        missing = sorted(c for c in cl if c not in shipped)
        w = sum(wsz.get(c, 0) for c in missing)
        z = sum(zsz.get(c, 0) for c in missing)
        rows.append((name, len(cl), len(missing), w, z, w + z))
    for r in sorted(rows, key=lambda r: r[3]):
        print(f"{r[0]:<10}{r[1]:>7}{r[2]:>11}{r[3]:>14,}{r[4]:>14,}{r[5]:>13,}")
    return rows


def main():
    wsz, zsz = load_sizes()
    shipped = set()
    weights = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "weights")
    for f in os.listdir(weights):
        if f.endswith(".rtbw"):
            shipped.add(f[:-5])
    print(f"already shipped as WDL: {len(shipped)} classes\n")

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--all-5man" in sys.argv:
        args = [k for k in wsz if sum(1 for c in k if c.isupper()) == 5]
    if not args:
        args = ["KRPvKR", "KBPvKB", "KPPvKN", "KRPvKN", "KRNvKP", "KQRvKN", "KRRvKR", "KBBvKN"]

    print("cost of adding each class, counting the capture/promotion closure,")
    print("and counting only files we do not already ship:\n")
    rows = report(args, wsz, zsz, shipped)

    budget = 50_000_000
    used = 1_588_504
    print(f"\nheadroom: {budget - used:,} bytes ({(budget - used) / 1e6:.1f} MB)")
    if len(rows) > 12:
        fits = [r for r in rows if r[3] < budget - used]
        print(f"5-man classes whose WDL closure fits the headroom on its own: {len(fits)} of {len(rows)}")


if __name__ == "__main__":
    main()
