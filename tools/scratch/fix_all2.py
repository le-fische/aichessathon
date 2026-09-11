import os
for path in ["baselines/numba_search_base/nsearch.py", "snapshots/match1_numba/nsearch.py", "snapshots/match2_old/nsearch.py"]:
    with open(path, 'r') as f:
        text = f.read()

    text = text.replace("depth = 1\n    prev_score = -1e9\n    \n    while depth <= max_depth:", "depth = 1\n    completed_depth = 0\n    prev_score = -1e9\n    \n    while depth <= max_depth:")

    with open(path, 'w') as f:
        f.write(text)
