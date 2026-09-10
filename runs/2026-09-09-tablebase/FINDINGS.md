# The live build never probes a tablebase at all

Worked on `danny-test`, 2026-09-09. Reproduce with `tools/tb_endgame_census.py`,
`tools/tb_probe_bench.py`, `tools/tb_probe_counter.py`,
`tools/tb_wdl_vs_dtz_gradient.py`, `tools/tb_endgame_playout.py`,
`tools/tb_insearch_probe_cost.py`.
Raw output: `census.txt`, `probe_bench.txt`, `probe_counter.txt`,
`wdl_vs_dtz_gradient.txt`, `playout_850ms.txt`, `playout_850ms_pass2.txt`,
`insearch_probe_cost.txt`.

All timings are LOCAL (this Mac, Python 3.13.5). The platform is one core of an
AMD EPYC 9V74 @ 2.60 GHz and its numbers will differ. Where a platform figure is
quoted it is labelled as such.

## Three verdicts

- **A. The 35 shipped `.rtbw` files are dead weight in the build that plays.**
  `chess.syzygy` is imported in `search.py` and nowhere else. The numba path
  issues zero probes. 1.3 MB of a 1.59 MB submission does nothing.
- **B. 5-man is still no**, but not for the reason the brief assumed. Probe time
  is affordable. The full set is out on size, and the engine already converts
  almost every 3-to-5-man ending it reaches without help.
- **C. Missing DTZ is real but narrow.** It costs us exactly one endgame class
  we cannot win at all: **KBNvK**.

## A. The headline: no probing in the shipping path

    $ for f in agent.py nsearch.py bitboard.py evaluation.py search.py; do
        echo "$f: $(grep -icE 'syzygy|tablebase|probe_wdl|rtbw' $f)"; done
    agent.py: 0
    nsearch.py: 0
    bitboard.py: 0
    evaluation.py: 0
    search.py: 4

    search.py:10:import chess.syzygy
    search.py:14:tb: chess.syzygy.Tablebase | None = None
    search.py:16:    tb = chess.syzygy.open_tablebase("weights")
    search.py:88:            wdl = tb.probe_wdl(ctx.board)

Counted at runtime by wrapping `probe_wdl`, over four endgame positions:

    === numba active (the live build) ===
    agent.USE_NUMBA_SEARCH = True
    KRvK   e8e4   0 probes
    KPvK   e1d1   0 probes
    KRvKP  e1e2   0 probes
    KQvKR  e2b5   0 probes
    total probe_wdl calls: 0

    === USE_NUMBA_SEARCH=0 (the python fallback) ===
    KRvK   e8g8   17484 probes
    KPvK   e1f2    3807 probes
    KRvKP  e1e2   20387 probes
    KQvKR  e2b5   16115 probes
    total probe_wdl calls: 57793

**`HANDOFF.md` is wrong about the current build.** It lists under Evaluation:
"Syzygy WDL for <= 4 pieces (35 files, 1.3 MB)". That describes `search.py`, the
fallback, which has not played a rated game since v10 went live on 8 September.

Consequences:

1. Every conclusion in `DANNY-LANE.md` section 6 and in the 8 Sept void
   write-up about "we ship WDL and no DTZ, so the search gets no gradient" is
   moot for the live build. There is no gradient because there is no probe.
2. The files are still dead weight the preflight should flag, alongside
   `karpov.npz`. They are cheap to keep (1.3 MB of 50 MB) and worth keeping
   only if someone wires them in.
3. Latent bug in the fallback, worth fixing whoever touches it:
   `open_tablebase("weights")` is a **relative** path resolved against the
   working directory, which the platform does not promise. It is wrapped in
   `contextlib.suppress(Exception)`, so if cwd is not the agent directory the
   fallback silently runs with `tb = None` and nobody finds out.

## B. Probe time is affordable; frequency is the whole question

Warm `probe_wdl`, 2000 reps per class:

| endgame | median us | = nodes of search |
|---|---|---|
| KRvK | 7.08 | 31 |
| KQvK | 7.42 | 32 |
| KPvKP | 13.67 | 59 |
| KPvK | 24.08 | 105 |
| KRvKN | 39.38 | 171 |
| KRvKP | 40.46 | 176 |
| KBNvK | 45.04 | 196 |
| KQvKR | 73.88 | 321 |
| KRPvKR (5-man) | 37.96 | 165 |
| KRRvKR (5-man) | 55.12 | 240 |
| KBBvKN (5-man) | 23.42 | 102 |
| KQRvKQ (5-man) | 32.92 | 143 |

Reference node rate 4,348,734 nodes/sec (3-man KRvK, local). **5-man probes are
not slower than 4-man probes** — 23 to 55 us against 7 to 74 us. Size, not
latency, is what separates them.

First touch is a one-off cost, not a per-probe cost: opening a `Tablebase`
object costs 0.32-0.63 ms, the first probe 3.9-13.3 ms, the second probe
14-79 us. Once a class is touched it stays in page cache. With 2 GB of RAM and
a 1.3 MB table set, everything we ship is effectively memory-resident, so the
"disk probe" framing in the brief does not apply at our scale.

The real constraint is how often you probe. From
`tools/tb_insearch_probe_cost.py`, including the ~2.6 us cost of rebuilding a
`chess.Board` from the numba position arrays (unavoidable: `chess.syzygy` cannot
be called from `njit` code and needs an `objmode` block):

    if a probe fired at EVERY node at <= 5 men, effective node rate would be:
      KRvK      98,780 nodes/sec   (41x slower)
      KPvK      37,798 nodes/sec  (106x slower)
      KRvKP     23,576 nodes/sec  (171x slower)
      KQvKR     13,267 nodes/sec  (303x slower)

So: probing at the root or within a ply or two of it is free. Probing in
quiescence would cost 40-300x the node rate and is out of the question. Any
implementation must gate on depth, not just on piece count.

Endgames are frequent enough to matter. Across 1191 plies of our 10 archived
games: **7.14% of plies had <= 4 men, 16.04% had <= 5 men.**

## C. WDL gives no gradient — demonstrated directly

`tools/tb_wdl_vs_dtz_gradient.py`, scoring every legal move by the flat
`20000 - ply` rule the fallback uses, against DTZ for the same child:

    KBNvK, the position the engine shuffles in
      7k/4BK2/8/5N2/8/8/8/8 w - - 80 41
      21 legal moves, ALL scoring exactly 19995
      distinct WDL-only scores: 1    distinct dtz: 4

Twenty-one moves, one score. The child DTZ values range from -3 to -11, so a
move that mates in 3 and a move that mates in 11 are indistinguishable. Same
shape from the KBNvK start position (2 distinct WDL scores vs 3 distinct DTZ)
and in KQvKR (3 vs 6).

## The measurement that decides it: does the engine actually need this?

Play-outs at `time_left_ms=10000` (850 ms per move), current build, against
DTZ-optimal ply counts:

| position | WDL | DTZ optimal plies | engine plies | outcome |
|---|---|---|---|---|
| KRvK-round17 | win | 21 | 23 | checkmate |
| KRvK-centre | win | 27 | 31 | checkmate |
| KQvK-centre | win | 13 | 13 | checkmate |
| KQvKR-won | win | 47 | 51 | checkmate |
| KRvKP-won | win | 25 | 27 | checkmate |
| KBBvK-corner | win | 33 | 35 | checkmate |
| KPvK-reallywon | win | 27 | 33 | checkmate |
| **KBNvK-corner** | win | 59 | **80** | **SHUFFLED, no result** |
| **KBNvK-b1start** | win | 57 | **100** | **SHUFFLED, no result** |
| KPvK-won | draw | - | 26 | drawn (correct) |
| KRPvKR-r31shape | (no table) | - | 52 | drawn |

**This is the finding that settles the question.** With no tablebase probing at
all, the engine converts seven of eight won endings, within 2 to 6 plies of
DTZ-optimal. `_mate_drive` is doing its job. Buying tablebase probing would buy
back those 2-6 plies, which are worth nothing at a 600-ply draw rule.

The one exception is **KBNvK**, which it cannot win from either start — 80 plies
and 100 plies of shuffling, both ending in the same corner position. KBN mate
needs a 30-plus-ply plan and no evaluation heuristic finds it.

Note also `KBNvK` has the slowest DTZ probe measured by a wide margin
(3656 us median, versus 24-291 us for every other class). Whatever fix targets
KBNvK cannot probe DTZ per node even at low depth.

## Recommendation

Ranked by value per hour, and none of these is the top priority in the repo
right now (that is the quiescence clock defect in
`runs/2026-09-09-longgame/FINDINGS.md`):

1. **Decide the 1.3 MB.** Either wire a root-only WDL+DTZ probe into the numba
   path, or delete `weights/*.rtbw` from the submission. Shipping them unread is
   the worst of the three options, and it has been the state of the build since
   8 September.
2. **If wiring it in: root-only, and for KBNvK specifically.** That is the one
   class where the engine gets zero result today. A root-only DTZ probe at
   <= 5 men, gated on depth so it never fires in quiescence, costs 165-321 nodes
   per move against a 3.5 M nodes/sec search — call it free.
3. **5-man WDL: no.** The full set is 378.1 MiB WDL-only against a 50 MB cap
   (chessprogramming.org/Syzygy_Bases). Cherry-picking is possible on latency
   grounds but pointless on value grounds: the engine already converts the 5-man
   endings it reaches. `KBPvKB` alone, the most common 5-man class in our
   archive at 91 plies, is 15.3 MB WDL.
4. **Fix the relative path** in `search.py:16` whether or not anything else
   changes.

## Not done

- The root-only probe was not implemented or A/B'd. No before/after exists.
- `n = 10` games for the endgame census, and one play-out per position. The
  KBNvK failure reproduced from two different starts, so that one is solid; the
  "converts within 2-6 plies" result is one sample per class.
- Play-outs ran at 850 ms per move, not the real time control.
