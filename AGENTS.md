# Working in this repo

This is a starter for AI Chessathon, a chess-engine competition. The deliverable is one file,
`agent.py`, exposing `get_move(fen, time_left_ms) -> str`. It gets zipped and uploaded, and the
platform plays it against other people's agents on a fixed cadence.

## Read the rules from the source

The competition rules and the agent contract live on the site and change. Fetch them before you
answer anything about limits, deadlines, or what is allowed:

- https://aichessathon.com/docs/agent-contract.md
- https://aichessathon.com/docs/rules.md

The quick reference below is a convenience for common questions. The two URLs are canonical
and they change, so fetch them before you rely on a number.

## The contract, in one place

- `agent.py` at the root of the zip, not inside a folder. The platform does `import agent`.
- `get_move(fen: str, time_left_ms: int) -> str` returning UCI, `e2e4` or `e7e8q`.
- Your colour is the side to move in the fen. There is no other input.
- The process starts once per game and stays alive between your moves. Module state survives to
  your next move in the same game, never to the next game.
- Import time has a 90 second budget before the clock starts. Load weights there.
- 120 s + 0.5 s per move, per side, on wall time. One core, 2 GB, no network, no GPU.
- Illegal move, malformed output, crash, out of memory, or flag fall loses that game. A move
  reply over 4 KB counts as illegal. A game still running at 600 plies is drawn.
- Everything in the zip together stays under 50 MB unzipped.
- Ten uploads per team per day, and the latest one that passed validation is the one that plays.
- Rated games start from curated opening positions, not the standard start. The set is not
  published.
- Your process is suspended while your opponent moves, so pondering is impossible: work you
  leave running between your own moves does not run. Each side has the core to itself while it
  thinks. Two of your games can run at once, in separate containers, and you are never asked
  for two moves at once.

## Things that break agents here

- The filesystem is read-only apart from 256 MB at `/tmp`. `HOME` and every cache path already
  point there; do not write anywhere else.
- No network at all. Nothing downloads at runtime. Weights ship inside the zip.
- One core. `torch.set_num_threads(1)`. More threads lose time rather than winning it.
- Your zip is first on `sys.path`. Never name a file after a module you import: `chess.py`,
  `types.py`, `random.py` will shadow the real one and the failure will look unrelated.
- The environment is fixed. The platform preinstalls torch 2.13 (CPU), numpy 2.5, python-chess
  1.11, onnxruntime 1.29 and numba 0.67 and installs nothing else. A `requirements.txt` is
  ignored, so an import outside that stack crashes on the platform even when it works locally.
  Additions can be requested at hello@aichessathon.com.
- Native binaries in the zip are rejected. Ship Python source. Model weights like `.onnx`,
  `.safetensors` and `.pt` are fine, and any model shipped must be one the team trained.
- numba is how Python gets fast here. Warm every jitted function once at import so compilation
  lands in the init budget, not on the clock. Cython does not work on the platform.
- `print` is safe. The runner points file descriptor 1 at stderr before importing the agent, so
  nothing you write can corrupt the protocol. It is kept, up to 8 KB (the first 4 KB and the
  last 4 KB), in the validation log and in a per-game log your dashboard offers alongside the
  PGN after every rated game. That log also carries your init time, your time on every move and
  the clock you had left, so it is a diagnostic channel worth not wasting: a per-move print can
  push the 8 KB over and lose the part you wanted.

## Do not

- Do not use Stockfish, Lc0, Maia, or any existing engine inside the submission, including a
  pip package that embeds one. It is an instant disqualification and it is checked after the
  fact. Training on data an engine annotated is allowed; the ban covers what ships and runs
  inside the zip.
- Do not add network calls, subprocess calls to external binaries, or anything that reads outside
  the agent directory and `/tmp`.
- Do not obfuscate. What ships has to be source a judge can read.
- Do not edit `harness/`. It mirrors the platform's protocol and clock. Changing it makes local
  results meaningless.

## Verify

```
make play      # one game against a baseline, real time control
make arena     # 20 fast games against a baseline, with a score
make zip       # build submission.zip with agent.py at the root
make gate      # ruff, mypy, and two games that have to finish cleanly
```

Nothing here decides whether an upload is accepted. The platform validates on upload and writes a
log to the dashboard; that log is the authority. The harness exists so local games are honest.

## Style

Python 3.12, type-annotated, ruff and mypy strict clean. Keep `agent.py` readable: it is the
thing a judge reads if your games get flagged, and the thing you have to explain at the final.
