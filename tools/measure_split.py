import os
import sys

sys.path.insert(0, os.path.abspath("."))
import search

qsearch_nodes = 0
negamax_nodes = 0
beta_cutoffs = 0
first_move_cutoffs = 0

original_qsearch = search.qsearch


def patched_qsearch(ctx, alpha, beta, ply):
    global qsearch_nodes
    qsearch_nodes += 1
    return original_qsearch(ctx, alpha, beta, ply)


search.qsearch = patched_qsearch

original_negamax = search.negamax


def patched_negamax(ctx, depth, ply, alpha, beta):
    global negamax_nodes, beta_cutoffs, first_move_cutoffs
    negamax_nodes += 1

    # We need to trace cutoffs inside negamax. We can't do it just by wrapping.
    # We have to patch search.py temporarily or read its code.
    return original_negamax(ctx, depth, ply, alpha, beta)


search.negamax = patched_negamax
