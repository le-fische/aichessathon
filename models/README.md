# models/

Trained artefacts that must stay in version control but must **not** ship.

`harness/package.py` builds the submission from the root `*.py` files plus `weights/`.
Anything in this directory is therefore tracked by git and absent from the zip. Put
trained networks here, not in `weights/`.

## karpov.npz

A 768x256x1 int16 NNUE network — the one `HANDOFF.md` describes as trained on positions
labelled locally by Stockfish 16.1. Four arrays:

    fc1_w   (256, 768)  int16
    fc1_b   (256,)      int16
    fc2_w   (1, 256)    int16
    fc2_b   (1,)        int16

**Nothing loads it, and it is the only copy in the repo.** Do not delete it on the
grounds that it is unreferenced.

`nsearch_nnue.py:14` loads `weights.npy`, `biases.npy` and `weights2.npy` from the
current working directory instead — different names, different shape convention. Those
three files do not exist on disk and `.gitignore` has `*.npy`, so they were never
committable. That mismatch is the "known bug to fix before NNUE can ship" in
`HANDOFF.md`; whoever fixes it should load from here with an explicit filename.

It lived in `weights/karpov.npz` until 2026-09-09 and so rode along in every submission
as 217,956 bytes of payload no shipped code reads. Moved out, kept in git. See
`runs/2026-09-09-preflight/FINDINGS.md` (check C07).
