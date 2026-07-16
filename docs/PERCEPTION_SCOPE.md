# Perception Scope and Validation Position

## What is implemented

The simulation provides a deterministic two-stage target-confirmation contract:

1. A coverage-complete gate permits an RGB candidate cue.
2. A separate thermal-confirmation stage publishes the target beacon after a delay.
3. The beacon contains target ID, position, confidence, urgency, sender ID, sender battery, timestamp and confirmation source.
4. The coordinator rejects confidence below 0.75.

This is appropriate for proving ROS integration, allocation, recovery and Digital Twin behavior without pretending that synthetic model accuracy is real-world accuracy.

## What is deliberately not claimed

- No trained detector consumes Gazebo camera pixels in the submitted prototype.
- No thermal classifier is benchmarked.
- The confidence value is scenario-controlled, not calibrated probability.
- No false-positive statistic is claimed from one deterministic target.

## Production replacement

The stable `/swarm/target_beacon` contract allows the simulation stage to be replaced by:

```text
RGB camera -> detector/tracker -> candidate ROI
Thermal camera -> calibration/registration -> temperature/shape confirmation
Pose + depth/GNSS -> world-coordinate localization
Fusion policy -> beacon or reject
```

Acceptance metrics would include per-sensor precision/recall, fused false-positive rate, miss rate, localization error, confirmation latency and performance by range/weather/temperature contrast.
