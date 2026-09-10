# What stands between 1700 and 2100

Research only. Nothing here has been changed. Every number below is measured from this
repo, our rated logs, or the tablebase listing -- not estimated.

Current: **rating 1700, peak 1835, rank #175 of 441 (top 40%)**. Top 50 needs roughly
2100, so the gap is **~400 Elo**.

---

## First: why "we beat Stockfish 2100" and "we are rated 1700" are both true

Two measurement problems, and both inflate our local numbers.

**1. `UCI_LimitStrength` is a weak yardstick.** Stockfish at `UCI_Elo 2100` searches at
FULL depth (measured: 18-19 ply at every anchor) and then *deliberately picks a worse
move at random*. It is a strong engine that throws pieces occasionally. An opponent that
never blunders farms those errors far more efficiently than a genuine 2100 would allow.
Beating it 78% does not mean 2321.

**2. The judge's machine is ~2.8x slower than this Mac.**

    cold import, local        11.2 - 11.5 s
    init on the platform      30.3 - 36.9 s   (mean 32.4 s, across 9 machines)

Every local benchmark, every Stockfish anchor, and every A/B has run at ~2.8x the speed
we actually get in a rated game. That is roughly **1.5 ply of search** we measure at home
and do not have on the platform.

**Neither is a reason to doubt the engine. Both are reasons to stop trusting the 2321.**

---

## Where the 400 Elo actually is, in measured order

### 1. The search tree is barely pruned -- this is the big one

    position      depth      nodes    EBF    depth at EBF 2.5
    opening           8    621,312   5.30    14.6   (+6.6 ply)
    middlegame        9  1,005,827   4.64    15.1   (+6.1 ply)
    sharp             8    688,353   5.37    14.7   (+6.7 ply)
    tactical          7    833,907   7.01    14.9   (+7.9 ply)
    endgame          13  1,180,679   2.93    15.3   (+2.3 ply)

Effective branching factor is `nodes^(1/depth)`. A well-pruned engine sits near **2.0-2.5**.
We are at **4.6-7.0 in the middlegame.**

We are already spending 2.2M nodes/sec. We are **spending them badly**: the same node
count at EBF 2.5 would reach **depth 14-15 instead of 7-9**. On the platform, at 2.8x
slower, our real rated depth is more like **6-8**.

Note the endgame row: EBF 2.93, depth 13. The pruning is fine when there are few pieces.
The failure is specifically the middlegame, where the branching is widest.

What a strong engine has that `nsearch.py` does **not** (verified by reading the file):

    null move pruning       PRESENT, but fixed R=3, no verification, no adaptive R
    killers / history       PRESENT
    counter-move history    PRESENT
    LMR                     PRESENT (v11 scaled it with depth and move number)
    SEE                     PRESENT in quiescence only
    -------------------------------------------------------------------
    aspiration windows      ABSENT
    futility pruning        ABSENT
    late move pruning       ABSENT
    razoring                ABSENT
    check extensions        ABSENT
    internal iterative deep ABSENT
    singular extensions     ABSENT
    SEE pruning in main     ABSENT

Eight standard techniques missing. Each is small and independently gateable -- exactly
the "little by little" shape this project has been working in. **This is where the Elo
is, and it is the cheapest Elo on the board.**

### 2. The evaluation has three terms

The entire shipped evaluation (`bitboard.evaluate`) is:

1. PeSTO piece-square tables (material + placement, tapered mg/eg)
2. Bishop pair (+30 mg / +50 eg)
3. Passed pawns + connected passed pawns

**That is all.** Absent: mobility, doubled pawns, isolated pawns, backward pawns, rook on
open/semi-open file, rook on 7th, knight outposts, threats, space, tempo. King safety was
built today and reverted after failing its A/B -- and the reason it failed is instructive:
it cost 0.40 ply, and *at EBF 5, a ply is expensive*. **Fixing the search first makes
evaluation terms cheaper to afford.** That ordering matters.

Le's unpushed doubled/isolated pawn work (`5963d9c`) belongs here.

### 3. NNUE: it was never actually tested

`models/nsearch_nnue.py:14`

    if os.path.exists("weights.npy"):
        weights = np.load("weights.npy")
        ...
    else:
        weights  = np.zeros((768, 256), dtype=np.int16)   # <-- all zeros
        biases   = np.zeros(256, dtype=np.int16)
        weights2 = np.zeros(512, dtype=np.int8)

`weights.npy` has never existed on disk, and `.gitignore` contains `*.npy`, so it never
could. **The else-branch always fired.** A zero-weight network scores every position
identically, which means the engine had no evaluation at all and was choosing essentially
arbitrarily. That is exactly what the three gates measured: **0/60, 1.0/43, 1 point in 57
games, ~-600 Elo.**

Meanwhile `models/karpov.npz` is a **real trained network** -- 768x256x1 int16, trained on
Stockfish-labelled positions:

    fc1_w  (256, 768) int16   97.4% nonzero, std 39.8, range -118..121
    fc1_b  (256,)     int16
    fc2_w  (1, 256)   int16   range -200..199
    fc2_b  (1,)       int16

It has **never been loaded by the code that was benchmarked.** The shapes also disagree
with what the loader expects (transposed fc1, and `weights2` declared as 512 int8 against
an actual (1,256) int16) -- further evidence the path never ran with real weights.

**So "NNUE is dead by measurement" is not established.** The measurement tested zeros. It
may still turn out worse than PeSTO once wired correctly, and a 256-neuron accumulator on
one core has a real speed cost to prove -- but that is an open question, not a closed one.
This is the single largest *unexplored* item we have.

### 4. Time management: we leave a fifth of the clock unused

    across 95 rated games
      mean clock left at end   28.8 s   (median 23.3 s)
      mean total budget       147.1 s
      -> 19.5% of our clock is never spent
      games ending under 10 s left: 15/95 (16%)

We are not in danger of flagging (v11: 0 of 167 moves over budget). We are being too
careful. A fifth of the thinking time is thrown away, and at EBF 5 buying even one extra
ply costs ~5x the nodes -- so unspent time is expensive here specifically.

There is no time-management *model* in the engine, just a fraction of the remaining clock.
A real one spends more in complex positions and near-instantly in forced ones.

### 5. We are flying blind on the platform

    OUTPUT
      147 bytes on stderr

The docs allow **8 KB** per game and the dashboard keeps it. We use 147 bytes -- three
warmup lines. A compact per-move line (depth, nodes, eval, time) at ~40 bytes would be
~2.3 KB in a 58-move game, comfortably inside the cap, and would tell us **the depth we
actually reach on the judge's machine** -- the number this whole document has to estimate
at 2.8x. This is zero risk to strength and it is the instrument every other decision needs.

### 6. Five-man tablebases: measured, and worth nothing

    games whose lowest piece count reached at most N men (21 rated games):
      <= 3 men    2/21 =  9.5%
      <= 4 men    2/21 =  9.5%    <- what v12 already ships
      <= 5 men    2/21 =  9.5%    <- 5-man adds ZERO games
      <= 6 men    5/21 = 23.8%
      <= 7 men    7/21 = 33.3%

**Every game that reaches 5 men also reaches 4 or fewer.** 5-man coverage adds **0.0%**.

The cost side is just as clear. We have 45.6 MB of headroom (submission is 4.44 MB of 50).
Full 5-man WDL is **394.8 MB** -- 74 of the 110 tables would fit, but they are the smallest
and therefore the most useless (KQQvKB, KRRRvK, KPPPvK -- positions our search already
wins trivially). The genuinely hard endings are the biggest files: KRPvKR 16.4 MB,
KQPvKQ 20.4 MB. And WDL alone provides no conversion gradient -- we proved that on KBNvK,
where all 21 legal moves scored an identical WDL against 4 distinct DTZ values -- so each
would need its DTZ partner too, from a 584.8 MB set. 6-man is 72 GB.

**Recommendation: drop this line permanently.** It is the item with the clearest negative
answer of anything examined today.

---

## Ranked, by Elo per unit of risk

    1. search pruning (8 missing techniques)  LARGE   low risk, individually gateable
    2. stderr instrumentation                 none    zero risk -- but unblocks everything
    3. time management model                  MEDIUM  low risk, pure clock arithmetic
    4. evaluation terms (pawns, mobility)     MEDIUM  low risk, cheaper AFTER item 1
    5. NNUE with the loader fixed             UNKNOWN medium risk, largest upside
    6. 5-man tablebases                       ZERO    measured -- do not do this

Items 1 and 3 are almost pure profit: they do not change what the engine *believes*, only
how deeply and for how long it looks. Item 4 is where king safety failed, and it failed
partly because item 1 had not been done first.

## Honest caveats

- The EBF figures come from 5 bench positions at 3 s each, on this Mac. They are a strong
  signal, not a tuned measurement.
- "~2.8x slower" is inferred from **JIT compile time**, not search throughput. Compilation
  is LLVM work and may not scale identically to the search loop. **Item 5 (stderr) would
  replace this inference with a measurement**, which is the main reason it is ranked so high.
- The endgame-frequency numbers rest on 21 archived games.
- Whether `karpov.npz` is any *good* is untested. The claim here is narrow: it was never
  tested, not that it works.
