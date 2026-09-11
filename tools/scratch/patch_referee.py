with open("harness/referee.py", "r") as f:
    text = f.read()

import re
text = re.sub(
    r'class Outcome\(NamedTuple\):\n    result: Result\n    termination: str\n    pgn: str',
    'class Outcome(NamedTuple):\n    result: Result\n    termination: str\n    pgn: str\n    white_clock: float = 0.0\n    black_clock: float = 0.0',
    text
)

# And pass the clock from play_match down to _outcome!
# We can just change play_match directly to add it to outcome since Outcome is a NamedTuple.
# Wait, Outcome(result, termination, pgn, white_clock, black_clock)
text = text.replace(
    'return _outcome(board, _decide(finish), finish.termination.name.lower())',
    'out = _outcome(board, _decide(finish), finish.termination.name.lower()); return Outcome(out.result, out.termination, out.pgn, clock[chess.WHITE], clock[chess.BLACK])'
)
text = text.replace(
    'return _outcome(board, _adjudicate(board), "adjudication")',
    'out = _outcome(board, _adjudicate(board), "adjudication"); return Outcome(out.result, out.termination, out.pgn, clock[chess.WHITE], clock[chess.BLACK])'
)
text = text.replace(
    'return _outcome(board, _opponent_wins(mover), failure.reason)',
    'out = _outcome(board, _opponent_wins(mover), failure.reason); return Outcome(out.result, out.termination, out.pgn, clock[chess.WHITE], clock[chess.BLACK])'
)
text = text.replace(
    'return _outcome(board, _opponent_wins(mover), "flag")',
    'out = _outcome(board, _opponent_wins(mover), "flag"); return Outcome(out.result, out.termination, out.pgn, clock[chess.WHITE], clock[chess.BLACK])'
)
text = text.replace(
    'return _outcome(board, _opponent_wins(mover), "illegal")',
    'out = _outcome(board, _opponent_wins(mover), "illegal"); return Outcome(out.result, out.termination, out.pgn, clock[chess.WHITE], clock[chess.BLACK])'
)

with open("harness/referee.py", "w") as f:
    f.write(text)
