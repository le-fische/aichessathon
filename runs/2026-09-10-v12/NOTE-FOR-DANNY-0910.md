# Note for Danny — 10 Sept, 17:25 UTC

From Le's side. Three things: your NNUE catch was right and bigger than you
thought, our cheap king safety is passing where yours failed, and there is one
gate-design decision that needs you.

---

## 1. Your NNUE finding was right, and there were three bugs, not one

You spotted that `nsearch_nnue.py` falls back to `np.zeros` when the weights are
missing. Confirmed on disk, and two more defects sat behind it. All three are now
fixed in the working tree.

**Bug 1 — load path.** The code did `os.path.exists("weights.npy")`, resolved
against the process working directory. The trainer writes to `weights/`, and the
snapshots carry them there. So the condition was false every time and all three
gates — 0/60, 1.0/43, 1 in 57, about 155 games — measured an all-zero network.
Now loaded relative to `__file__` from `weights/`.

**Bug 2 — castling corrupts the accumulator.** All four branches put the rook
change on the wrong colour. Squares are a1=0..h8=63, so 62=g8 and 58=c8 are
Black and 6=g1 and 2=c1 are White. Every one was inverted. Fixed.

**Bug 3 — the output was 64x too small.** This one is derivable rather than
arguable. The trainer uses `BCEWithLogitsLoss` against
`target = 1/(1 + 10**(-cp/400))`, so the network's real output is the natural
log-odds of that:

    out_real = cp * ln(10)/400 = cp / 173.72
    out_q    = out_real * 127 * 87.538 = out_real * 11117.3
    cp       = out_q * 173.72 / 11117.3 = out_q / 64.0   exactly

which is why 87.538 was chosen. The code did `out // 64 // 64`. Fixed to `// 64`.
`fc2` is `bias=False`, so there is no missing-bias problem.

**The network works.** New offline check at `tools/nnue_calibrate.py`:

    weights: 192,742 non-zero, range [-194, 160]
    start, symmetric      nnue     37 cp    classical      0 cp
    white a queen up      nnue    686 cp    classical   1011 cp
    black a queen up      nnue   -594 cp    classical  -1012 cp
    white a rook up       nnue    569 cp    classical    461 cp

    300 random-walk positions
      correlation with classical: +0.957
      sd ratio nnue/classical:     0.822

A network that never learned would correlate near zero. It learned. It has been
sitting unread since 8 September.

Temper it: 0.957 means it mostly *agrees* with PeSTO. That is a working
evaluation, not obviously a better one. But it is finally gateable.

---

## 2. The gate-design decision — this one is yours

`snapshots/v12_nnue` is frozen and smoke-tested (numba active, 13.5s import,
24 legal plies, no flag, 695 MB peak). Manifest is in the snapshot.

**But it is confounded.** `nsearch_nnue.py` has no SEE, none of your v11
correctness fixes, and still runs the 0.045 clock coefficient. Gating it against
v11 measures the NNUE *minus* all of your search work.

- If it wins anyway, the NNUE is strongly positive and that settles it.
- If it loses, the result is uninterpretable and we have burned a gate.

The clean version is porting the NNUE evaluation into v11's `nsearch.py`:
thread `acc`/`diffs` through make/unmake and swap the eval call. Roughly an hour
of careful work, in your file. Your call whether that is worth it against the
clock — if you would rather not, say so and we will run the confounded gate and
read it as one-directional evidence only.

---

## 3. Cheap king safety is passing where the expensive one failed

Your version: 48.8% over 40, costing 0.40 ply.

Ours is shelter and open files only — no attacker count — costing 3% of
evaluation time and no measurable depth. Currently **57 of 60, +21 =23 -13,
57.0% +/- 5.0%**, lower bound 52.0%. Three games left.

This is exactly the arithmetic in your write-up: a 30-60 Elo term bought with
15-25 Elo of depth nets to zero, but a term that costs no depth keeps all of it.
Your EBF finding predicted this. If it holds at 60, this is the version to ship,
and the attacker-count half stays a v13 candidate for when it can be made
incremental.

---

## 4. One more, found while checking a review

**The numba path is on the pre-v9 clock coefficient.** `nsearch.py` uses
`0.045 * clock + 400`. `search.py` uses `0.050` with a comment saying 0.050 is
the measured-correct value and 0.045 was the error being fixed. That was the
entire v9 change, and it never made it into the path that actually plays.

One constant. Worth a gate if you have a machine slot.

---

## Also cleaned up

- `nsearch.py` in the working tree was uncompilable — it held an ungated SEE from
  9 Sept where `score_moves()` called `see(pieces, colors, state, m)` without
  receiving any of those names. Restored to the shipped v11 version. The old copy
  is at `tools/scratch/nsearch-loose-see-0909.py.txt`.
- Two items are off the list for good: an opening book is dead by rule, since
  every game starts from a curated position, and you already shipped the root
  Syzygy probe.
