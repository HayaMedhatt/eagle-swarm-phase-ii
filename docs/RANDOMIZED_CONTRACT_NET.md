# Randomized Coverage and Deterministic Contract-Net

## Coverage planning

Random coverage is constrained, not uncontrolled. Each robot has a launch point and a safe angular wedge. A seeded planner samples a radial step, computes all goals, then rejects the set unless pairwise goal separation exceeds the configured threshold.

```text
scout_1:  -15 to +15 degrees
worker_1: +45 to +70 degrees
relay_1:  -70 to -45 degrees
step:      2.5 to 3.5 m
minimum planned goal separation: 2.8 m
```

The mission logs the seed, goals and planned minimum separation. This gives natural-looking runs while retaining exact replay for evaluation.

## Allocation remains deterministic

The random coverage changes each robot's distance to the target and therefore the bids, but the selection is deterministic for the observed state:

```text
total = distance + battery_penalty + role_penalty + link_penalty
```

The coordinator uses lowest total cost and robot ID as a stable tie-break. Randomness never decides the winner directly.
