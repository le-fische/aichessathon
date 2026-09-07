import time
import numpy as np
from numba import njit

def bench_separate(weights1, weights2, acc, N):
    w1 = weights1
    w2 = weights2
    a = acc.copy()
    
    t0 = time.time()
    for i in range(N):
        from_idx = i % 768
        to_idx = (i + 1) % 768
        a -= w1[from_idx]
        a += w1[to_idx]
    t1 = time.time()
    
    for i in range(N):
        hidden = np.clip(a, 0, 127)
        out = np.dot(hidden, w2)
    t2 = time.time()
    
    return t1 - t0, t2 - t1

def bench_fused(weights1, weights2, acc, N):
    w1 = weights1
    w2 = weights2
    a = acc.copy()
    
    t0 = time.time()
    for i in range(N):
        from_idx = i % 768
        to_idx = (i + 1) % 768
        a += w1[to_idx] - w1[from_idx]
    t1 = time.time()
    
    for i in range(N):
        out = np.dot(np.clip(a, 0, 127), w2)
    t2 = time.time()
    
    return t1 - t0, t2 - t1

@njit(cache=True)
def numba_update(w1, a, N):
    for i in range(N):
        from_idx = i % 768
        to_idx = (i + 1) % 768
        for j in range(256):
            a[j] = a[j] - w1[from_idx, j] + w1[to_idx, j]

@njit(cache=True)
def numba_eval(w2, a, N):
    out = 0
    for i in range(N):
        s = 0
        for j in range(256):
            val = a[j]
            if val < 0: val = 0
            elif val > 127: val = 127
            s += val * w2[j]
        out = s
    return out

def bench_from_scratch(weights1, N):
    w1 = weights1
    
    t0 = time.time()
    for i in range(N):
        # Average 32 pieces on board
        indices = np.arange(i % 700, (i % 700) + 32)
        a = np.sum(w1[indices], axis=0)
    t1 = time.time()
    return t1 - t0

def run_benches():
    N = 300000
    print(f"Benchmarking {N} iterations...")
    
    np.random.seed(42)
    weights1 = np.random.randint(-127, 127, size=(768, 256), dtype=np.int16)
    weights2 = np.random.randint(-127, 127, size=(256,), dtype=np.int16)
    acc = np.zeros(256, dtype=np.int32)
    
    upd_sep, eval_sep = bench_separate(weights1, weights2, acc, N)
    print(f"\nNumpy Separate:")
    print(f"  Update: {N/upd_sep:,.0f} ops/sec")
    print(f"  Eval  : {N/eval_sep:,.0f} ops/sec")
    print(f"  Total : {N/(upd_sep + eval_sep):,.0f} evals/sec")
    
    upd_fus, eval_fus = bench_fused(weights1, weights2, acc, N)
    print(f"\nNumpy Fused:")
    print(f"  Update: {N/upd_fus:,.0f} ops/sec")
    print(f"  Eval  : {N/eval_fus:,.0f} ops/sec")
    print(f"  Total : {N/(upd_fus + eval_fus):,.0f} evals/sec")
    
    # Warmup
    numba_update(weights1, acc.copy(), 1)
    numba_eval(weights2, acc.copy(), 1)
    
    t0 = time.time()
    numba_update(weights1, acc.copy(), N)
    t1 = time.time()
    
    t2 = time.time()
    numba_eval(weights2, acc.copy(), N)
    t3 = time.time()
    
    print(f"\nNumba JIT:")
    print(f"  Update: {N/(t1-t0):,.0f} ops/sec")
    print(f"  Eval  : {N/(t3-t2):,.0f} ops/sec")
    print(f"  Total : {N/(t1-t0 + t3-t2):,.0f} evals/sec")
    
    scratch_t = bench_from_scratch(weights1, N)
    print(f"\nFrom Scratch (Numpy sum 32 vectors):")
    print(f"  Update: {N/scratch_t:,.0f} ops/sec")

if __name__ == '__main__':
    run_benches()
