"""Flag safety of the shipped time policy, with the panic path removed.

The new policy deletes the `time_left_ms < 3000` panic branch on the grounds
that the simulation stabilises above 3000 ms. That is a safety net being
removed because a model says it will not be needed, so the model is worth
checking against the platform's real limits: 120 s + 0.5 s per move, and
adjudication at 300 plies, i.e. up to 150 moves per side.
"""


def new_policy(time_left_ms: float, fullmove: int) -> float:
    moves_to_go = max(20.0, 60.0 - fullmove)
    budget = time_left_ms / moves_to_go + 250.0
    return min(budget, time_left_ms * 0.8)


def old_policy(time_left_ms: float, fullmove: int) -> float:
    if time_left_ms < 3000:
        return min(200.0, time_left_ms * 0.1)
    return min(time_left_ms * 0.045 + 400.0, time_left_ms * 0.25)


for label, policy in (("current (live v5)", old_policy), ("new (moves-to-go)", new_policy)):
    print(f"\n{label}")
    for overshoot in (1.0, 1.25, 1.5):
        time_left = 120_000.0
        minimum = time_left
        flagged_at = None
        for move in range(1, 151):
            budget = policy(time_left, move)
            # The search runs to hard_stop = 0.85 * budget and can overrun the
            # last iteration; overshoot models spending more than budgeted.
            time_left -= budget * overshoot
            time_left += 500.0
            minimum = min(minimum, time_left)
            if time_left <= 0:
                flagged_at = move
                break
        state = f"FLAGGED at move {flagged_at}" if flagged_at else "survived 150 moves"
        print(f"  spend x{overshoot:<5} {state:<24} minimum left {minimum:9.1f} ms")
