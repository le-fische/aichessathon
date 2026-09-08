# ruff: noqa
import os
import sys
import time

version_dir = sys.argv[1]  # e.g. "versions/v1-philidor"
fen = sys.argv[2]
budget = float(sys.argv[3])  # e.g. 3000

sys.path.insert(0, os.path.abspath(version_dir))

import agent as agent_mod  # noqa: E402
import search as search_mod  # noqa: E402

global_nodes = 0
selective_depth = 0

if hasattr(search_mod, "qsearch"):
    original_qsearch = search_mod.qsearch

    def patched_qsearch(ctx, alpha, beta, ply):
        global selective_depth
        if ply > selective_depth:
            selective_depth = ply
        return original_qsearch(ctx, alpha, beta, ply)

    search_mod.qsearch = patched_qsearch

original_negamax = search_mod.negamax


def patched_negamax(ctx, depth, ply, alpha, beta):
    global selective_depth
    if ply > selective_depth:
        selective_depth = ply
    return original_negamax(ctx, depth, ply, alpha, beta)


search_mod.negamax = patched_negamax

original_init = search_mod.SearchContext.__init__


def patched_init(self, board, time_budget, *args):
    original_init(self, board, time_budget, *args)
    self.time_budget = budget
    self.hard_stop = budget * 0.85


search_mod.SearchContext.__init__ = patched_init


def patched_check_time(self):
    global global_nodes
    global_nodes += 1
    self.nodes += 1
    if self.nodes % 256 == 0 and (time.monotonic() - self.start_time) * 1000 >= self.hard_stop:
        raise search_mod.TimeUp()


search_mod.SearchContext.check_time = patched_check_time

start = time.monotonic()
agent_mod.get_move(fen, 60000)
end = time.monotonic()

elapsed = end - start
nps = global_nodes / elapsed if elapsed > 0 else 0

completed_depth = getattr(search_mod, "completed_depth", "N/A")

print(f"{version_dir} | {budget}ms | FEN: {fen}")
print(f"Nodes: {global_nodes}")
print(f"Completed Iterative Deepening Depth: {completed_depth}")
print(f"Selective Depth (Max Ply): {selective_depth}")
print(f"Elapsed: {elapsed:.3f}s")
print(f"NPS: {nps:.0f}")
