# 15-Minute Assessment Demonstration Script

## Preparation

Use one reproducible seed and keep the browser dashboard, Gazebo and terminal log visible. Clear old processes and confirm the target platform is at `(10, 0)`.

```bash
cd ~/eagle_swarm_ws
./scripts/stop_integrated_demo.sh || true
COVERAGE_SEED=2180021560 ./scripts/start_integrated_demo.sh
```

## 0:00-1:15 - Architecture and safety boundary

Show `architecture_diagram.pdf`. State:

- ROS 2/DDS is the mission and swarm layer.
- MAVROS is the boundary to three independent PX4 SITL instances.
- Four coordinator replicas observe identical state; only the elected owner's replica awards tasks.
- Battery, GPS, separation and landing precedence remain onboard each aerial adapter and cannot be overridden by Contract-Net.

## 1:15-3:15 - Startup and three-aircraft flight

Show three FCU links, takeoff and hover. Point out health gating: the mission does not issue sector commands until all three report `ACTIVE`.

## 3:15-4:30 - Randomized coverage partition

Show the logged seed and three distinct fan-out paths. Explain that randomness is constrained by role-specific angular wedges, radial bounds and a minimum pairwise-goal separation. The same seed reproduces the run.

## 4:30-5:30 - Target confirmation contract

Narrate two independent stages:

1. RGB cue creates a candidate only.
2. Thermal confirmation authorizes a beacon with position, confidence, urgency, sender, battery and timestamp.

Be explicit that this is deterministic simulation perception, not a claim of trained model accuracy.

## 5:30-7:00 - Contract-Net and Ground Relay

Pause on four bids. Sum distance, battery, role and link components for two candidates and show why the lowest total wins. Point out that the Ground Relay participates through the same unchanged messages and generic agent class.

## 7:00-8:15 - Target execution and safe landing

Show the winner flying directly to the physical target platform. The winner lands vertically on the platform; non-winners return to their own launch positions and land. Wait for all three `LANDED` heartbeats and `DEMO COMPLETE`.

## 8:15-9:15 - Collision safety

Show the generated separation evidence from `run_separation_acceptance.sh`: controlled crossing goals, `SEPARATION_INTERVENTION` (or `NEAR_MISS`) and `SEPARATION_CLEAR`. Explain the independent 3-D monitor, deterministic yielding priority, hold command, release margin and delayed-hold protection during landing.

## 9:15-11:00 - Coordinator-loss recovery

Use the generated coordinator-loss evidence timeline. Show initial leader, injection, disabled colocated replica, new leader epoch and measured recovery duration. Emphasize that the mission nodes and other replicas never stop.

## 11:00-13:30 - Remaining mandatory faults

Present the machine-generated evidence index:

- winner shutdown -> timeout -> re-award;
- critical battery -> RTB/landing -> re-award;
- Wi-Fi cut -> onboard hold -> DDS rejoin;
- GPS dropout -> local safe hold -> resumed state.

For each, show detection, action and recovery time rather than only source code.

## 13:30-14:20 - Digital Twin and interfaces

Show member cards, leader epoch, target, bid breakdown, award, fault and safety timelines. Demonstrate `ros2 action list` and the single role-change service.

## 14:20-15:00 - Limitations and next steps

State the limitations confidently:

- deterministic perception contract rather than camera-model evaluation;
- reactive separation rules rather than full ORCA;
- simulated battery/charging rotation;
- single-machine DDS/Gazebo rather than RF/network hardware-in-the-loop.

Close with the production plan: real sensor nodes behind unchanged interfaces, authenticated DDS, VIO fallback, hardware watchdogs and HIL validation.
