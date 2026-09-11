with open("harness/referee.py", "r") as f:
    text = f.read()

text = text.replace(
    'class Outcome:\n    result: Result\n    termination: str\n    pgn: str',
    'class Outcome:\n    result: Result\n    termination: str\n    pgn: str\n    white_clock: float = 0.0\n    black_clock: float = 0.0'
)

# And pass the clocks down from play_match
# Restore what we messed up
import re
text = re.sub(
    r'out = _outcome\(board, _decide\(finish\), finish\.termination\.name\.lower\(\)\); return Outcome\(out\.result, out\.termination, out\.pgn, clock\[chess\.WHITE\], clock\[chess\.BLACK\]\)',
    'return _outcome(board, _decide(finish), finish.termination.name.lower())',
    text
)
text = re.sub(
    r'out = _outcome\(board, _adjudicate\(board\), "adjudication"\); return Outcome\(out\.result, out\.termination, out\.pgn, clock\[chess\.WHITE\], clock\[chess\.BLACK\]\)',
    'return _outcome(board, _adjudicate(board), "adjudication")',
    text
)
text = re.sub(
    r'out = _outcome\(board, _opponent_wins\(mover\), failure\.reason\); return Outcome\(out\.result, out\.termination, out\.pgn, clock\[chess\.WHITE\], clock\[chess\.BLACK\]\)',
    'return _outcome(board, _opponent_wins(mover), failure.reason)',
    text
)
text = re.sub(
    r'out = _outcome\(board, _opponent_wins\(mover\), "flag"\); return Outcome\(out\.result, out\.termination, out\.pgn, clock\[chess\.WHITE\], clock\[chess\.BLACK\]\)',
    'return _outcome(board, _opponent_wins(mover), "flag")',
    text
)
text = re.sub(
    r'out = _outcome\(board, _opponent_wins\(mover\), "illegal"\); return Outcome\(out\.result, out\.termination, out\.pgn, clock\[chess\.WHITE\], clock\[chess\.BLACK\]\)',
    'return _outcome(board, _opponent_wins(mover), "illegal")',
    text
)

# Now just patch _outcome signature and creation
text = text.replace(
    'def _outcome(board: chess.Board, result: Result, termination: str) -> Outcome:',
    'def _outcome(board: chess.Board, result: Result, termination: str, white_clock: float = 0.0, black_clock: float = 0.0) -> Outcome:'
)
text = text.replace(
    'return Outcome(result=result, termination=termination, pgn=str(game))',
    'return Outcome(result=result, termination=termination, pgn=str(game), white_clock=white_clock, black_clock=black_clock)'
)

# And now pass them from play_match
text = text.replace(
    'return _outcome(board, "black", white_failure)',
    'return _outcome(board, "black", white_failure, 0.0, 0.0)'
)
text = text.replace(
    'return _outcome(board, "white", black_failure)',
    'return _outcome(board, "white", black_failure, 0.0, 0.0)'
)
text = text.replace(
    'return _outcome(board, _decide(finish), finish.termination.name.lower())',
    'return _outcome(board, _decide(finish), finish.termination.name.lower(), clock.get(chess.WHITE, 0.0), clock.get(chess.BLACK, 0.0))'
)
text = text.replace(
    'return _outcome(board, _adjudicate(board), "adjudication")',
    'return _outcome(board, _adjudicate(board), "adjudication", clock.get(chess.WHITE, 0.0), clock.get(chess.BLACK, 0.0))'
)
text = text.replace(
    'return _outcome(board, _opponent_wins(mover), failure.reason)',
    'return _outcome(board, _opponent_wins(mover), failure.reason, clock.get(chess.WHITE, 0.0), clock.get(chess.BLACK, 0.0))'
)
text = text.replace(
    'return _outcome(board, _opponent_wins(mover), "flag")',
    'return _outcome(board, _opponent_wins(mover), "flag", clock.get(chess.WHITE, 0.0), clock.get(chess.BLACK, 0.0))'
)
text = text.replace(
    'return _outcome(board, _opponent_wins(mover), "illegal")',
    'return _outcome(board, _opponent_wins(mover), "illegal", clock.get(chess.WHITE, 0.0), clock.get(chess.BLACK, 0.0))'
)

with open("harness/referee.py", "w") as f:
    f.write(text)
