# Numba Bitboard Integration Plan

## 1. The Python-Numba Boundary & Expected Speedup

In `perft`, the boundary is crossed exactly once per search tree: we call into `perft` from Python, and it runs recursively purely inside Numba. That's why it achieves a 50-55x speedup over `python-chess`.

In a staged integration, the Python-to-Numba boundary would sit at every single node. The workflow would be:
1. Numba: `generate_pseudo_legal_moves` (returns Numpy array of moves)
2. Python: Iterates over moves, move ordering, TT probe
3. Numba: `make_move`
4. Python: Call `evaluate` (if leaf) or recurse
5. Numba: `unmake_move`

The overhead of crossing the JIT boundary (unboxing arguments, returning numpy arrays) takes on the order of ~0.5 microseconds per call.

If we speed up movegen infinitely but still leave the boundary at every node, our node rate will not jump to 2.5x. Movegen is only ~30% of search time. Amdahl's Law on 30% alone caps the speedup at `1 / (1 - 0.30) = 1.43x`.

To achieve a 2.5x to 3.5x end-to-end speedup, we **must** port both movegen (30%) and evaluation (50%) into Numba (see Section 2). With 80% of the work in Numba, the remaining Python logic (TT, ordering, loop overhead) takes ~20%, setting the theoretical ceiling at 5x. Boundary overhead will pull this realistic figure down to roughly 2.5x to 3.5x. This is still sufficient to buy 2-3 extra plies of depth.

## 2. Evaluation inside Numba

Yes, evaluation **must** move into Numba. As derived above, if evaluation remains in Python, our overall speedup cannot exceed 1.43x.

By porting evaluation into Numba:
1. We eliminate a boundary crossing.
2. We compile the tight loop of piece-square table lookups and material counting to machine code.
3. This allows the evaluation function to operate directly on the `pieces` and `colors` integer arrays without needing to translate back to Python lists or `chess.Board`.

## 3. Transposition Table and Zobrist Hashing

Since `board._transposition_key()` is tied to `python-chess`, we must implement a custom Zobrist hashing scheme in Numba. 

**Implementation Details:**
- **Initialization:** During import, we initialize a 64x12 matrix of random 64-bit integers for the pieces, plus random numbers for turn, castling rights (16 combinations), and en passant files (8).
- **Tracking:** We will add a `zobrist_key` field to the `state` array passed around in `make_move`/`unmake_move`. 
- **Incremental Updates:** Inside `make_move`, as we use XOR (`^=`) on the piece bitboards, we will simultaneously XOR the corresponding piece-square hashes into the `zobrist_key`. Castling rights and turn bits are also XOR'd incrementally.
- This costs virtually zero extra time per node and allows the Python search layer to probe the TT using the `state[4]` value (the hash).

## 4. `agent.py` Synchronization & Fallback

The platform interfaces with our bot via `get_move(fen, time_left_ms)`. 

**Failure Mode:** If the Numba engine and the `python-chess` engine diverge silently, we might return an illegal move and instantly lose the game.

**Architecture:**
- `agent.py` will maintain a `python-chess` board that only tracks the *actual* game state received by `get_move(fen)`. 
- When `get_move` is called, we read the FEN into the `python-chess` board and convert it to our Numba integer arrays.
- The entire search runs purely on the Numba arrays. It does not touch the `python-chess` board.
- Once the search returns a best move, `agent.py` translates it back to a UCI string using `decode_move`.

**Validation and Fallback:** Before `get_move` returns, it explicitly checks if the decoded move is present in `board.legal_moves`. If the Numba engine hallucinates an illegal move due to a bug, we log the error and fall back to:
1. The best move from the previous completed iterative deepening iteration.
2. A material-greedy pick.
3. The first legal move in `list(board.legal_moves)`.

## 5. Equivalence Test

Any change in move ordering changes which branches alpha-beta prunes, so node counts will legitimately differ. Node identity is the wrong gate for this integration. The core assertion is that the search reaches identical conclusions, even if it traverses a different tree shape. 

We will write `tests/test_equivalence.py`:
1. Load a suite of 20 middle-game FENs and a few tactical FENs where a single ply changes the answer.
2. Run the legacy `python-chess` search to `depth=4` and record the root score.
3. Run the new Numba-integrated search to `depth=4`.
4. **Assert:** The root score is identical between the two engines.
5. **Assert:** The returned move's own score equals that root score (accounting for ties where the engine might pick a different but equally-scored move).
6. Log the node count and TT hits purely as a diagnostic.

## 6. Warmup and JIT Failure Mitigation

**Warmup:** The `bitboard.py` module includes a `warmup()` routine which forces Numba to compile all `@njit` functions during module initialization. Currently, this costs 2.293s (measured locally on macOS) of the 90s init budget (using ~2.2% of the budget). We must ensure that every single jitted function (including the new Numba evaluation function) receives a real call during `warmup()` so no compilation penalties land on the game clock.

**JIT Failure on Platform:** If `numba` fails to compile on the platform's hardware or exceeds the init budget, the crash would cost us the entire submission. We will guard the import with a `try/except` block and use a fallback flag. If Numba is unavailable, `agent.py` will fall back to using the legacy `python-chess` search. This makes it completely safe to ship the integration, as we are not betting the ladder on the platform environment perfectly supporting our Numba routines.

## 7. Staged Port vs Full Search Port

**The Assumption:** The staged approach leaves the core search algorithm (negamax, quiescence, TT probes) in Python, setting a hard ceiling of 1-2 Mnps due to boundary crossings. 

**Full Search Port:** Porting the search itself entirely into Numba removes the per-node boundary and puts us back in the regime where perft runs at 26 Mnps. This would yield a massive speedup well beyond 2-3 plies.

**Why the Staged Approach First?**
A full search port requires rewriting complex search logic and implementing a fixed-size numpy array with replacement for the transposition table instead of a Python dict. This is a large, high-risk piece of work. With rosters locking on September 11, the staged approach comes first because it reliably secures 2-3 plies of depth and can be shipped safely behind the fallback flag. Once the staged version is validated on the ladder, the full Numba search port becomes the immediate next priority if time permits.
