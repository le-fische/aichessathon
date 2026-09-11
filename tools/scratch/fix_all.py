import os
for path in ["baselines/numba_search_base/nsearch.py", "snapshots/match1_numba/nsearch.py", "snapshots/match2_old/nsearch.py"]:
    with open(path, 'r') as f:
        text = f.read()

    text = text.replace("return 0, 0.0, 0\n", "return 0, 0.0, 0, 0\n")
    text = text.replace("return best_move, prev_score, nodes[0]\n", "return best_move, prev_score, nodes[0], completed_depth\n")
    text = text.replace("return best_move, prev_score, nodes[0], completed_depth, completed_depth", "return best_move, prev_score, nodes[0], completed_depth")

    if "completed_depth = 0\n    while depth" not in text:
        text = text.replace("depth = 1\n    while depth <= max_depth:", "depth = 1\n    completed_depth = 0\n    while depth <= max_depth:")

    with open(path, 'w') as f:
        f.write(text)
