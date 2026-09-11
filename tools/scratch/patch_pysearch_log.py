import re
fpath = "baselines/python_search/search.py"
with open(fpath, 'r') as f:
    text = f.read()

if "import sys\n    print" in text:
    text = text.replace("import sys\n    print", "import sys\n    import os\n    if os.environ.get('CHESSATHON_DEPTH_LOG') == '1':\n        print")
with open(fpath, 'w') as f:
    f.write(text)
