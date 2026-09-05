def current_policy(time_left_ms):
    if time_left_ms < 3000:
        budget_ms = min(200.0, time_left_ms * 0.1)
    else:
        budget_ms = min(time_left_ms * 0.045 + 400.0, time_left_ms * 0.25)
    return budget_ms
    
def candidate_policy_opt(time_left_ms):
    # A time management strategy tailored for 120s + 0.5s increment and long games
    moves_to_go = max(20.0, time_left_ms / 3000.0) 
    budget = time_left_ms / 35.0 + 350.0
    return min(budget, time_left_ms * 0.5)

def simulate(policy, max_moves):
    time_left = 120000.0
    increment = 500.0
    
    print(f"{policy.__name__}:")
    for m in range(1, max_moves + 1):
        budget = policy(time_left)
        if m == 1:
            print(f"  Move   1: budget {budget:6.1f} ms, time left {time_left:8.1f} ms")
        time_left -= budget
        time_left += increment
        if time_left <= 0:
            print(f"  FLAGGED at move {m}")
            return
        if m % 40 == 0:
            print(f"  Move {m:3}: budget {budget:6.1f} ms, time left {time_left:8.1f} ms")

for p in [current_policy, candidate_policy_opt]:
    simulate(p, 200)
    print()
