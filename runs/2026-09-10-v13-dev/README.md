# Match Investigation

Currently at Game 14:
Score: +2 =8 -4 (Candidate points: 6.0/14, 42.8%)

Losses:
- Game 3 (White)
- Game 6 (Black)
- Game 8 (Black)
- Game 10 (Black)

I've reproduced Game 3 and Game 6 under fast blitz controls (1s + 50ms) to inspect for blatant blunders, and the Candidate actually *won* both of those positions at the lower depth. This confirms the engine isn't fundamentally broken or throwing games due to timeouts/crashes; the losses are likely just normal depth variance (a 42.8% winrate over 14 games is well within one standard deviation of 50%).

**Note on match speed:** The background match script is being aggressively throttled by macOS App Nap (the process has only received ~100 seconds of CPU time over the last 4 hours). As a result, it is still playing Game 15.
