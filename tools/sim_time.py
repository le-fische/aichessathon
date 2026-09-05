def policy_moves_to_go_50(time_left_ms, fullmove):
    moves_to_go = max(20.0, 50.0 - fullmove)
    budget = time_left_ms / moves_to_go + 350.0
    return min(budget, time_left_ms * 0.8)

def policy_moves_to_go_60(time_left_ms, fullmove):
    moves_to_go = max(20.0, 60.0 - fullmove)
    budget = time_left_ms / moves_to_go + 250.0
    return min(budget, time_left_ms * 0.8)

def simulate(policy, max_moves):
    time_left = 120000.0
    increment = 500.0
    fullmove = 1
    
    print(f"{policy.__name__}:")
    
    min_time = time_left
    
    for m in range(1, max_moves + 1):
        budget = policy(time_left, fullmove)
        
        # Calculate actual spend
        spent = budget
        
        time_left -= spent
        time_left += increment
        
        if time_left < min_time:
            min_time = time_left
            
        if time_left <= 0:
            print(f"  FLAGGED at move {m}")
            return
            
        if m == 1 or m == 20 or m % 40 == 0:
            print(f"  Move {m:3}: budget {budget:6.1f} ms, time left {time_left:8.1f} ms")
            
        fullmove += 1

    print(f"  Minimum time remaining: {min_time:8.1f} ms")
    print()

for p in [policy_moves_to_go_50, policy_moves_to_go_60]:
    simulate(p, 200)
def policy_moves_to_go_40(time_left_ms, fullmove):
    moves_to_go = max(20.0, 40.0 - fullmove)
    budget = time_left_ms / moves_to_go + 150.0
    return min(budget, time_left_ms * 0.8)

simulate(policy_moves_to_go_40, 200)
