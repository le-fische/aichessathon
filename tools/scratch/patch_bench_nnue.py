with open("tools/bench_nnue_forward.py", "r") as f:
    text = f.read()

text = text.replace("""@njit
def bench_classical(pieces_arr, colors_arr, state_arr, n):
    t0 = time.time()
    s = 0
    for i in range(n):
        s += bitboard.evaluate(pieces_arr[i], colors_arr[i], state_arr[i])
    t1 = time.time()
    return t1 - t0, s

@njit
def bench_nnue_full(pieces_arr, colors_arr, state_arr, n, weights, biases, weights2):
    acc = np.zeros((2, 256), dtype=np.int16)
    t0 = time.time()
    s = 0
    for i in range(n):
        nnue_full_refresh(pieces_arr[i], colors_arr[i], weights, biases, acc)
        turn = state_arr[i][0]
        s += nnue_eval(weights2, acc, turn)
    t1 = time.time()
    return t1 - t0, s

@njit
def bench_nnue_inc(moves_arr, turns_arr, is_make_arr, n, weights, weights2, initial_acc, initial_turn):
    acc = initial_acc.copy()
    diffs = np.zeros((6, 4), dtype=np.int8)
    
    t0 = time.time()
    s = 0
    for i in range(n):
        move = moves_arr[i]
        turn = turns_arr[i]
        is_make = is_make_arr[i]
        
        count = extract_diffs(move, turn, diffs)
        if not is_make:
            for j in range(count):
                diffs[j, 0] = -diffs[j, 0]
                
        apply_diffs(weights, acc, diffs, count)
        
        if is_make:
            s += nnue_eval(weights2, acc, turn ^ 1)
            
    t1 = time.time()
    return t1 - t0, s""", """@njit(cache=True)
def loop_classical(pieces_arr, colors_arr, state_arr, n):
    s = 0
    for i in range(n):
        s += bitboard.evaluate(pieces_arr[i], colors_arr[i], state_arr[i])
    return s

def bench_classical(pieces_arr, colors_arr, state_arr, n):
    t0 = time.time()
    s = loop_classical(pieces_arr, colors_arr, state_arr, n)
    t1 = time.time()
    return t1 - t0, s

@njit(cache=True)
def loop_nnue_full(pieces_arr, colors_arr, state_arr, n, weights, biases, weights2):
    acc = np.zeros((2, 256), dtype=np.int16)
    s = 0
    for i in range(n):
        nnue_full_refresh(pieces_arr[i], colors_arr[i], weights, biases, acc)
        turn = state_arr[i][0]
        s += nnue_eval(weights2, acc, turn)
    return s

def bench_nnue_full(pieces_arr, colors_arr, state_arr, n, weights, biases, weights2):
    t0 = time.time()
    s = loop_nnue_full(pieces_arr, colors_arr, state_arr, n, weights, biases, weights2)
    t1 = time.time()
    return t1 - t0, s

@njit(cache=True)
def loop_nnue_inc(moves_arr, turns_arr, is_make_arr, n, weights, weights2, initial_acc):
    acc = initial_acc.copy()
    diffs = np.zeros((6, 4), dtype=np.int8)
    s = 0
    for i in range(n):
        move = moves_arr[i]
        turn = turns_arr[i]
        is_make = is_make_arr[i]
        
        count = extract_diffs(move, turn, diffs)
        if not is_make:
            for j in range(count):
                diffs[j, 0] = -diffs[j, 0]
                
        apply_diffs(weights, acc, diffs, count)
        
        if is_make:
            s += nnue_eval(weights2, acc, turn ^ 1)
    return s

def bench_nnue_inc(moves_arr, turns_arr, is_make_arr, n, weights, weights2, initial_acc, initial_turn):
    t0 = time.time()
    s = loop_nnue_inc(moves_arr, turns_arr, is_make_arr, n, weights, weights2, initial_acc)
    t1 = time.time()
    return t1 - t0, s""")

# Let's also change depth from 4 to 3 to be faster? 
# 1.6M states is fine, it should take ~1 second to evaluate. Let's keep depth=4 for more accuracy!
# Wait, FEN 2 might have more. Let's make it 3 if we want it to finish fast. I'll change to depth=4 but restrict the number of perft iterations to max out at depth 3 for the first FEN if needed.
# Actually 1.6 million states at 1 million evals/sec is 1.6s. It's totally fine.

with open("tools/bench_nnue_forward.py", "w") as f:
    f.write(text)
