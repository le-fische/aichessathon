# v7-tal: Repetition and Contempt Research

This branch parks the research and implementation we did on threefold repetition avoidance and contempt. We pulled this forward during v2 development but are parking it here to stick to the roadmap (v3 is next).

## Key Findings

1. **Structural Blindness to Game History:**
   `search.get_move` initializes the board strictly from the provided FEN (`board = chess.Board(fen)`). Since FENs do not carry a move stack, `board.is_repetition(2)` inside the search can only ever detect repetitions occurring entirely *within* the search tree itself. It is completely blind to whether a position has already occurred earlier in the actual game.

2. **The Fix (Stateful History):**
   To fix this, `agent.py` must maintain a persistent `collections.Counter` of positions seen. It must record both the position it was asked to move in, AND the position resulting from the move it returns. (Since we only check for repetition after pushing our candidate move during search, we are checking opponent-to-move positions, so we need those opponent-to-move positions in our history).

3. **Repetition Frequencies:**
   In normal play (measured over a 300-ply game), `count == 1` (a position seen once before) fires about 6 times per game at the root. `count >= 2` (a position about to be repeated for the third time, triggering a draw claim) almost *never* fires in normal play against a different engine.

4. **Contempt and Penalties:**
   We experimented with `CONTEMPT = -40.0` (for threefold repetition) and `NEAR_REPETITION_PENALTY = 15.0` (for twofold repetition). We measured a sharp regression (22.5% winrate) when applying this logic.
   
5. **Jitter vs. Behavior:**
   A deep dive into move selection showed **zero divergence** across 50 positions between the baseline engine and the repetition-avoidance engine. The regression was actually caused by:
   a) A separate bug (accidentally replacing `_transposition_key()` with the 25x slower `zobrist_hash()`).
   b) A `NameError` crash when removing instrumentation, hidden by `agent.py`'s exception handler.
   c) OS scheduling jitter! Because iterative deepening was bounded by `time.monotonic()`, the two engines would occasionally search to different depths (e.g., stopping at depth 5 vs depth 6). Once they diverged, they played a real game where small sample sizes (like 5 games) showed wild variance.

## Fixed-Node Testing
To solve the jitter problem, we introduced the `SEARCH_MAX_NODES` environment variable. When set, `SearchContext` strictly bounds the search by nodes rather than wall-clock time. This makes A/B testing perfectly deterministic.
