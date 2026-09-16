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

### 1. The search tree is under-pruned -- still the big one, but smaller than first stated

> **CORRECTED 10 Sept 18:20.** The first version of this section reported EBF 4.6-7.0 and
> depth 7-9 from `tools/bench_v11.py`. Both were artefacts of the tool.
> `bench_v11.py` passes its `--ms` value as the engine's **`time_left_ms`**, not as the
> search budget. `numba_search` then computes
> `budget_ms = min(3000*0.045+400, 3000*0.25) = 535 ms` and aborts at 85% of it, so those
> "3-second" benchmarks actually ran **0.29-0.45 s**. EBF is high on a truncated search
> because the shallow iterations dominate. The numbers below come from the 600-ply
> endurance trajectory instead -- real games, real budgets, 299 measured plies.

    source                             depth        EBF
    bench_v11.py (0.29-0.45 s)          7-9      4.64-7.01   <- ARTEFACT, do not cite
    real games (299 plies)             11-15      3.23 mean
                                                  3.31 median

Effective branching factor is `nodes^(1/depth)`. A well-pruned engine sits near **2.0-2.5**.
We are at **3.23**, and we reach **depth 11-15** in real games -- up to 23 in endgames.

So the search is **mediocre, not broken**. At a constant node count:

    EBF 3.23 -> depth 13.0     (where we are)
    EBF 3.00 -> depth 13.8     (+0.9 ply)
    EBF 2.50 -> depth 16.6     (+3.6 ply)
    EBF 2.00 -> depth 21.9     (+9.0 ply)

Realistically this item is worth **about +3 ply**, not the +6-8 first claimed. It is still
the largest lever on this list, and the correction does not change its rank.

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
    check extensions        PRESENT (nsearch.py:448, `ply < 2*root_depth`) -- CORRECTED
    internal iterative deep ABSENT
    singular extensions     ABSENT
    SEE pruning in main     ABSENT

Seven standard techniques missing (check extensions were wrongly listed as absent in the
first version of this document; they are at `nsearch.py:448`). Each is small and independently gateable -- exactly
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
it cost 0.40 ply, and a ply is expensive here. **Fixing the search first makes
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

### 4. Time management: real, but worth far less than it looks -- DEMOTED

    across 95 rated games
      mean clock left at end   28.8 s   (median 23.3 s)
      mean total budget       147.1 s
      -> 19.5% of our clock is never spent
      games ending under 10 s left: 15/95 (16%)

> **DEMOTED 10 Sept 18:20.** The first version ranked this "medium Elo". Priced properly
> against the corrected EBF it is worth almost nothing, and a 40-game A/B could not detect
> it. 19.5% *sounds* large; depth is logarithmic in nodes.

    extra nodes    extra ply at EBF 3.23
           20%          0.15            <- all our unspent clock
          100%          0.59
          200%          0.94

**Spending every second we currently leave on the table buys 0.15 ply.** To gain one ply
from time alone we would need **3.23x the clock**, which does not exist. Compare item 1:
fixing the branching factor is +3.6 ply. That is a **20x** difference, and it is why
pruning outranks this by so much.

What might still be worth something is *redistribution* rather than volume -- there is no
time-management model, just a fraction of the remaining clock, and spending 2x on critical
positions is a different change from spending 20% more everywhere. That needs a model and
a way to detect complexity, so it is v13 work at best.

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

    1. search pruning (7 missing techniques)  ~+3 ply  low risk, individually gateable
    2. stderr instrumentation                 none     zero risk -- but unblocks everything
    3. evaluation terms (pawns, mobility)     MEDIUM   low risk, cheaper AFTER item 1
    4. NNUE with the loader fixed             UNKNOWN  medium risk, largest upside
    5. time management                        ~0.15ply DEMOTED -- undetectable in 40 games
    6. 5-man tablebases                       ZERO     measured -- do not do this

Item 1 is the closest thing to pure profit: it does not change what the engine *believes*,
only how deep it gets for the same nodes. Item 3 is where king safety failed, and it
failed partly because item 1 had not been done first -- an evaluation term has to be paid
for in ply, so the cheaper a ply gets, the more evaluation we can afford.

## Honest caveats

- The EBF figure of 3.23 comes from the 600-ply endurance trajectory: 299 plies of one
  self-play game on this Mac. It replaces the earlier bench_v11 figure, which was an
  artefact of that tool passing `--ms` as `time_left_ms` (see item 1). One game is a
  strong signal, not a tuned measurement across many.
- "~2.8x slower" is inferred from **JIT compile time**, not search throughput. Compilation
  is LLVM work and may not scale identically to the search loop. **Item 5 (stderr) would
  replace this inference with a measurement**, which is the main reason it is ranked so high.
- The endgame-frequency numbers rest on 21 archived games.
- Whether `karpov.npz` is any *good* is untested. The claim here is narrow: it was never
  tested, not that it works.
