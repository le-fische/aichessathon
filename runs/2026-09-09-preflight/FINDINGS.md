# `tools/preflight.py`: one real defect in the current submission, and 4 warnings

Worked on `danny-test`, 2026-09-09. Run it with:

    ~/Desktop/AIChessHackathon/pyenv/bin/python tools/preflight.py

13 checks, ~2 minutes. `--full` runs a 128-ply game at the real time control,
`--no-runtime` is static only, `--zip PATH` audits an already-built zip.

It builds the zip from `git show HEAD:<file>` into a staging directory, never
from the working tree (HANDOFF's upload checklist), then asserts against the
*unzipped* archive.

## Verdict on the current HEAD (64862b1)

    13 checks: 8 pass, 4 warn, 1 fail, 0 skipped
    FAILED: C07
    Do not upload.

### The one failure

    [FAIL] C07  Every file under weights/ is actually loaded by shipped code
             scan: weights/ [.rtbw, .rtbz] from search.py:16
             35/36 data files are reachable from shipped code
             DEAD WEIGHT: weights/karpov.npz (217,956 bytes) is shipped and
                          referenced by no shipped .py
             217,956 bytes of unreferenced payload in every upload

This is the file `dc1fdc4` ("drop dead weight from the submission") was supposed
to remove and did not. It is still in the HEAD tree, so `package.py` still ships
it. **Fix: `git rm --cached weights/karpov.npz` and add it to `.gitignore`.**
Not done here — this session does not run state-changing git commands.

Note the check handles the directory-scan case correctly: it reads
`open_tablebase("weights")` at `search.py:16`, infers the `.rtbw`/`.rtbz` glob,
and clears all 35 tablebase files without a false positive. Only `karpov.npz`
is left unexplained.

### The four warnings, in order of how much they matter

**C02 — two shipped modules that nothing imports.**

    7 root .py: agent.py, bitboard.py, evaluation.py, nnue.py, nsearch.py,
                nsearch_nnue.py, search.py
    ships but is not imported by agent.py: nnue.py, nsearch_nnue.py
                (package.py globs every root *.py)

`nnue.py` and `nsearch_nnue.py` ride along in every upload and are unreachable
from `agent.py`. Harmless in size terms; they are also the NNUE work in
progress, so this is a warning rather than a failure. Worth a decision before
the 11 Sept lock: if NNUE is not shipping, they should not be in the zip.

**C00b — `harness/rules.py` disagrees with the live docs.**

    INIT_BUDGET_S = 60, live docs say 90  (harness is read-only; do not edit)
    PLY_CAP = 300, live docs say 600      (harness is read-only; do not edit)

Every local result routed through the harness inherits a 300-ply cap with
material adjudication instead of a 600-ply draw. This is the defect that would
have silently truncated the long-game experiment; see
`runs/2026-09-09-longgame/FINDINGS.md`. Reported for the owner of `harness/`;
HANDOFF forbids editing it, so the check warns rather than patching.

**C08 — two unlatched prints in an except handler.**

    ok (once-latch):  agent.py:56, :58, :100, :101
    ok (env-guard):   nsearch.py:534, search.py:473
    unlatched except-handler output (repeats if it keeps failing):
                      agent.py:123 print()
                      agent.py:124 traceback.print_exc()
    16 import-time output call(s) -- once per game, not on the clock

The rule the check applies, and why: import-time output is fine (once per game,
inside the 90 s init budget). Inside the per-move call graph — 39 functions,
resolved transitively from `get_move` — an output call must be either behind an
env flag that is false when unset, inside a once-per-game latch, or inside an
except handler whose latch an enclosing `if` tests. Unlatched handler output is
a warning, not a failure, because it only fires when something is already going
wrong; but `agent.py:123-124` is the *top-level* handler, so if the agent enters
a persistent bad state it prints a full traceback every move for the rest of the
game.

That matters more than previously believed: **stderr is not discarded in rated
games.** The live docs say it is kept, up to 8 KB, in a dashboard log alongside
the PGN, carrying init time, per-move time and clock left. A repeating traceback
would blow the 8 KB cap and destroy the most useful diagnostic channel we have,
in exactly the game where we would want to read it. `CLAUDE.md` and `HANDOFF.md`
both say stderr is discarded and are wrong.

**C09/C10 — local/platform skew, stated rather than hidden.**

    local python is 3.13; the platform runs 3.12
    cold import 11.0s locally; judge/local ratio for v10 was 28.4/11.0 = 2.58x,
    so expect ~28.4s on the judge against a 90s budget (32%)
    agent.USE_NUMBA_SEARCH is True with no environment variable set

### What passed

    [PASS] C00   limits verified 2026-09-09 against agent-contract.md + rules.md
    [PASS] C01   agent.py is a top-level member
    [PASS] C03   7 .py names checked against 295 stdlib + permitted names
    [PASS] C04   43 members scanned; no ELF / Mach-O / PE headers
    [PASS] C05   1,588,504 bytes unzipped = 3.18% of 50,000,000
    [PASS] C06   14 distinct top-level imports, all stdlib/permitted/shipped
    [PASS] C11/C12  24 plies, clock left W 12,383 / B 9,326 ms,
                    peak RSS 596 MB of 2048 (29.1%)
    [PASS] C13   43 shipped files all byte-identical to HEAD, 0 drifted

C00 hard-codes the limits with the source and the fetch date, and reports its
own age, so it starts warning when the numbers get stale.

## Proof the checks can fail

House rule 3: a check that is true by construction is not a check. Each was
broken deliberately in a doctored copy of the staged zip under `/tmp`, never in
the repo root.

| broken | result |
|---|---|
| `agent.py` moved into `sub/` | `[FAIL] C01  agent.py is NOT at the zip root; the platform does 'import agent'` |
| `scratch_probe.py` added at root | `[FAIL] C02  UNEXPECTED root .py in the zip: scratch_probe.py  (scratch files ship; see HANDOFF rule 8)` |
| `chess.py` added at root | `[FAIL] C03  No shipped file shadows a stdlib or permitted-package module` |
| `helper.so` with a real ELF header | `[FAIL] C04  No native binaries (magic bytes, not extension alone)` |
| 51 MB `weights/fat.rtbw` | `[FAIL] C05  Unzipped size is under the 50 MB cap` |
| `import requests` prepended to `evaluation.py` | `[FAIL] C06  import 'requests' in evaluation is not stdlib, not shipped, and not one of ['chess', 'numba', 'numpy', 'onnxruntime', 'torch']` |
| `weights/karpov.npz` restored | `[FAIL] C07  DEAD WEIGHT: weights/karpov.npz (217,956 bytes)` |

Two notes on the negative testing itself, for honesty:

- The first C06 attempt appended the import to the end of `evaluation.py`, which
  concatenated onto the last line and was caught by `C06a Every shipped .py
  parses` instead. That was a flaw in the test, not the check. Re-run with the
  import prepended, and C06 fires correctly (above).
- The C04 and C01 cases also trip C07, because a planted `helper.so` and a
  planted `sub/` directory are, correctly, unreferenced payload. Not a false
  positive.

## Lint and types

    $ ruff check tools/preflight.py
    All checks passed!
    $ mypy --strict tools/preflight.py
    Success: no issues found in 1 source file

## Recommendation on `tools/verify_zip.py`

**Delete it.** It asserts the zip contains exactly
`{agent.py, search.py, evaluation.py}`. A real submission has 7 root `.py`
files plus 36 files under `weights/`, so it rejects every valid build — and a
check that always fails gets ignored, which is worse than no check. Everything
it intended to do, `preflight.py` now does against the unzipped archive.
`tools/check_root.py` can stay; it is a fast subset and it is what HANDOFF's
checklist names.

Not deleted here: this session does not run state-changing git commands.

## Not done

- Never run on the platform. Every runtime number above is local, on Python
  3.13 against the platform's 3.12.
- C11/C12 defaults to a 24-ply smoke game so the whole script finishes in about
  two minutes. `--full` (128 plies at the real time control) has not been run.
- The check does not verify that a shipped `.onnx`/`.pt`/`.safetensors` model is
  one the team trained. That is a rules requirement and it is not automatable.
