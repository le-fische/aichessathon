"""What does it cost the numba search to leave njit and ask Python a question?

The live engine (agent.py -> nsearch.py -> bitboard.py) is entirely @njit. A
Syzygy probe is pure Python (chess.syzygy), so any probe from inside the search
has to cross an `objmode` boundary. This measures that boundary on its own,
before the probe itself is paid for.

Usage:  python tools/tb_objmode_cost.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from numba import njit, objmode

N = 200_000


@njit(cache=False)
def loop_plain(n):
    acc = 0.0
    for i in range(n):
        acc += i * 0.5
    return acc


@njit(cache=False)
def loop_objmode(n):
    acc = 0.0
    for i in range(n):
        with objmode(t="float64"):
            t = 1.0
        acc += t
    return acc


@njit(cache=False)
def loop_objmode_time(n):
    acc = 0.0
    for i in range(n):
        with objmode(t="float64"):
            t = time.time()
        acc += t
    return acc


@njit(cache=False)
def loop_objmode_callback(n, buf):
    acc = 0.0
    for i in range(n):
        with objmode(t="float64"):
            t = _probe_stub(buf)
        acc += t
    return acc


def _probe_stub(buf):
    """Stand-in for a probe: hand an array to Python, get a float back."""
    return float(buf[0])


def timed(fn, *args):
    fn(*args[:-1], 100) if False else None
    return None


def run(label, fn, *args):
    fn(*args)  # compile + warm
    t0 = time.perf_counter()
    fn(*args)
    dt = time.perf_counter() - t0
    per = dt / N * 1e6
    print(f"{label:<34}{dt:>9.4f} s{per:>12.3f} us/iter")
    return per


def main():
    print(f"iterations per measurement: {N:,}\n")
    print(f"{'what':<34}{'total':>11}{'per iter':>16}")
    plain = run("njit loop, no objmode", loop_plain, N)
    om = run("njit loop, objmode returning 1.0", loop_objmode, N)
    omt = run("njit loop, objmode time.time()", loop_objmode_time, N)
    buf = np.zeros(8, dtype=np.int64)
    omc = run("njit loop, objmode python call", loop_objmode_callback, N, buf)
    print()
    print(f"bare objmode round trip:      {om - plain:.3f} us")
    print(f"objmode + time.time():        {omt - plain:.3f} us")
    print(f"objmode + trivial py call:    {omc - plain:.3f} us")


if __name__ == "__main__":
    main()
