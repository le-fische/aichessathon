def current_policy(time_left_ms):
    if time_left_ms < 3000:
        budget_ms = min(200.0, time_left_ms * 0.1)
    else:
        budget_ms = min(time_left_ms * 0.045 + 400.0, time_left_ms * 0.25)
    return budget_ms

time_left = 120000.0
for m in range(1, 142):
    budget = current_policy(time_left)
    if m >= 132:
        print(f"Move {m:3}: budget {budget:6.1f} ms, time_left {time_left:6.1f} ms")
    time_left -= budget
    time_left += 500.0

