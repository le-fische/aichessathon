# Numba Bitboard Integration Plan

## 1. The Python-Numba Boundary & Expected Speedup

In `perft`, the boundary is crossed exactly once per search tree: we call into `perft` from Python, and it runs recursively purely inside Numba. That's why it achieves a 50-55x speedup over `python-chess`.

In a real alpha-beta search without moving the entire search algorithm into Numba, the Python-to-Numba boundary would sit at every single node. The workflow would be:
1. Numba: `generate_pseudo_legal_moves` (returns Numpy array of moves)
2. Python: Iterates over moves, move ordering, TT probe
3. Numba: `make_move`
4. Python: Call `evaluate` (if leaf) or recurse
5. Numba: `unmake_move`

The overhead of crossing the JIT boundary (unboxing arguments, returning numpy arrays) takes on the order of ~0.5 microseconds per call. Doing this 2-3 times per node limits the max theoretical node rate to roughly 500,000 to 1,000,000 nodes per second (1-2 Mnps), completely irrespective of how fast the bitboard logic itself is.

Given that move generation previously took ~30% of the time and evaluation took ~50% of the time (putting python-chess node generation at ~58,000 nps), if we speed up movegen infinitely but still leave the boundary at every node, our node rate will jump from ~58k to perhaps ~150k-200k nps, yielding a 2.5x to 3.5x end-to-end speedup. This is sufficient to buy 2-3 extra plies of depth.

## 2. Evaluation inside Numba

Yes, evaluation **must** move into Numba. If evaluation (which takes ~50% of the time) remains in Python, Amdahl's Law dictates our overall speedup cannot exceed 2x (since 50% of the baseline time remains untouched).

By porting evaluation (which relies entirely on counting material and piece-square tables) into Numba:
1. We eliminate a boundary crossing.
2. We compile the tight loop of piece-square table lookups and material counting to machine code.
3. This allows the evaluation function to operate directly on the `pieces` and `colors` integer arrays without needing to translate back to Python lists or `chess.Board`.

Since the recent bitboard evaluation patch landed, porting this to Numba is just a matter of changing the signatures and using integer operations, moving evaluation into `bitboard.py` or a jitted `evaluation.py`.

## 3. Transposition Table and Zobrist Hashing

Since `board._transposition_key()` is tied to `python-chess`, we must implement a custom Zobrist hashing scheme in Numba. 

**Implementation Details:**
- **Initialization:** During import, we initialize a 64x12 matrix of random 64-bit integers for the pieces, plus random numbers for turn, castling rights (16 combinations), and en passant files (8).
- **Tracking:** We will add a `zobrist_key` field to the `state` array passed around in `make_move`/`unmake_move`. 
- **Incremental Updates:** Inside `make_move`, as we use XOR (`^=`) on the piece bitboards, we will simultaneously XOR the corresponding piece-square hashes into the `zobrist_key`. Castling rights and turn bits are also XOR'd incrementally.
- This costs virtually zero extra time per node and allows the Python search layer to probe the TT using the `state[4]` value (the hash).

## 4. `agent.py` Synchronization

The platform interfaces with our bot via `get_move(fen, time_left_ms)`. 

**Failure Mode:** If the Numba engine and the `python-chess` engine diverge silently, we might return a move string like `e2e4` which `python-chess` considers legal, but the Numba board considered a capture. If the Numba engine corrupts its state, it will start playing illegal moves and we instantly lose the game.

**Architecture:**
- `agent.py` will maintain a `python-chess` board that only tracks the *actual* game state received by `get_move(fen)`. 
- When `get_move` is called, we read the FEN into the `python-chess` board.
- We then call `from_chess_board(board)` to convert the position into our Numba integer arrays (`pieces`, `colors`, `state`).
- The entire search runs purely on the Numba arrays. It does not touch the `python-chess` board at all.
- Once the search returns a best move (encoded as a 32-bit integer), `agent.py` translates it back to a UCI string using `decode_move`.
- **Validation step:** Before `get_move` returns, it explicitly checks if the decoded move is present in `board.legal_moves`. If the Numba engine hallucinates an illegal move due to a bug, we log the error and fall back to picking `random.choice(list(board.legal_moves))` so we don't crash and lose the game.

## 5. Equivalence Test

To prove the integration didn't subtly change what the engine plays (e.g. by generating moves in a different order, causing alpha-beta to prune differently):

We will write `tests/test_equivalence.py`:
1. It loads a suite of 20 middle-game FENs.
2. It runs the legacy `python-chess` search to `depth=4` and records the exact total node count, transposition table hits, and the best move chosen.
3. It runs the new Numba-integrated search to `depth=4` on the same FENs.
4. It asserts that for every FEN, the returned move is identical, the node count is identical, and the final evaluation scores match perfectly.
5. If move ordering changes because of how `generate_pseudo_legal_moves` loops over pieces, node counts might differ slightly, but the returned best move and score must remain provably identical.
