# EAGLE SWARM — Phase II Practical Assessment

> **Private assessment repository.** This project contains confidential candidate work prepared for CYRKIL Robotics. Do not redistribute it or make the repository public without written permission.

A reproducible **ROS 2 + PX4 SITL + Gazebo** prototype for a three-UAV civilian reconnaissance swarm, with a scored Ground Relay extension, distributed leader election, Contract-Net task allocation, collision-safety behavior, battery-aware return-to-base, fault injection, and a browser-based Digital Twin.

## Demonstrated capabilities

- Three independent PX4 SITL x500 vehicles in one Gazebo environment.
- Health-gated startup for Gazebo, PX4, MAVROS, and the ROS 2 swarm graph.
- Constrained randomized coverage movement with a logged reproducibility seed.
- Deterministic RGB cue followed by simulated thermal confirmation.
- `/swarm/target_beacon`, `/swarm/bids`, and `/swarm/task_award` communication.
- Explainable Contract-Net cost:

  ```text
  distance + battery_penalty + role_penalty + link_quality_penalty
  ```

- Replicated coordinator logic and heartbeat-based leader election.
- Winner lands on the physical target platform; non-winners return to their launch points.
- Virtual battery depletion, critical-battery RTB, task release, and re-auction.
- Active separation intervention with hold/resume hysteresis and near-miss logging.
- Ground Relay participation through the same heartbeat, bid, award, and election contracts.
- Runtime evidence generation with measured recovery times.

## Supported environment

- Ubuntu 22.04 LTS
- ROS 2 Humble
- Python 3.10+
- PX4-Autopilot SITL at `~/PX4-Autopilot`
- Gazebo Sim compatible with the PX4 checkout
- MAVROS and MAVROS Extras
- Git and GitHub CLI (`gh`)

## Repository architecture

```text
eagle_swarm_ws/
├── .github/
│   └── workflows/
│       └── static-validation.yml
├── docs/
│   ├── TECHNICAL_REPORT.pdf
│   ├── architecture_diagram.pdf
│   ├── REQUIREMENTS_TRACEABILITY.md
│   ├── FAULT_TEST_MATRIX.md
│   ├── DEMO_SCRIPT.md
│   ├── TECHNICAL_DEFENSE.md
│   ├── SAFETY_SECURITY.md
│   ├── ASSESSMENT_SCORECARD.md
│   └── REVIEWER_QUICKSTART.md
├── evidence/
│   ├── baseline_normal/
│   ├── runtime/                    # generated locally; ignored by Git
│   └── README.md
├── scripts/
│   ├── start_integrated_demo.sh
│   ├── stop_integrated_demo.sh
│   ├── run_fault_scenario.sh
│   ├── run_fault_campaign.sh
│   ├── run_full_acceptance_campaign.sh
│   ├── run_separation_acceptance.sh
│   ├── preflight_submission.sh
│   ├── final_submission_gate.sh
│   └── package_submission.sh
├── src/
│   ├── eagle_swarm_common/         # reusable policies and unit tests
│   ├── eagle_swarm_msgs/           # custom topics, service, and action
│   ├── eagle_swarm_core/           # mission, agents, auction, leader election
│   ├── eagle_swarm_px4/            # PX4/MAVROS adapters and onboard safety
│   ├── eagle_swarm_sim/            # Gazebo world, target, safety monitor
│   ├── eagle_swarm_dashboard/      # browser and terminal Digital Twin
│   └── eagle_swarm_tools/          # fault injection and evidence reporting
├── .gitignore
├── README.md
└── requirements-dev.txt
```

## ROS 2 package responsibilities

| Package | Responsibility |
|---|---|
| `eagle_swarm_common` | ROS-independent allocation, coverage, election, and safety policies |
| `eagle_swarm_msgs` | Heartbeat, beacon, bid, award, leader, fault, safety, role-change, and action interfaces |
| `eagle_swarm_core` | Mission orchestration, agents, replicated coordinators, role routing, and actions |
| `eagle_swarm_px4` | Per-aircraft MAVROS/PX4 bridge and onboard safety-authority boundary |
| `eagle_swarm_sim` | Gazebo assets and independent three-dimensional separation monitoring |
| `eagle_swarm_dashboard` | Browser and terminal Digital Twin views |
| `eagle_swarm_tools` | Fault injector, automated scenario runner, and evidence summarizer |

## 1. Install dependencies

Initialize `rosdep` once on a new machine:

```bash
sudo rosdep init
rosdep update
```

Install project dependencies:

```bash
cd ~/eagle_swarm_ws
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
sudo apt install -y python3-pytest
```

## 2. Build and test

```bash
cd ~/eagle_swarm_ws
source /opt/ros/humble/setup.bash
rm -rf build install log
colcon build --symlink-install
source install/setup.bash
```

Run ROS package tests:

```bash
colcon test
colcon test-result --verbose
```

Run policy and evidence tests directly:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=src/eagle_swarm_common:src/eagle_swarm_tools \
python3 -m pytest -q -p no:cacheprovider \
  src/eagle_swarm_common/test/test_policy.py \
  src/eagle_swarm_common/test/test_coverage.py \
  src/eagle_swarm_tools/test/test_evidence_report.py
```

## 3. Run the normal integrated mission

```bash
cd ~/eagle_swarm_ws
source /opt/ros/humble/setup.bash
source install/setup.bash

AUTO_LAND=true \
OPEN_DASHBOARD=1 \
TARGET_X=10.0 \
TARGET_Y=0.0 \
COVERAGE_SEED=9003 \
./scripts/start_integrated_demo.sh
```

Dashboard:

```text
http://127.0.0.1:8080
```

Follow the mission log:

```bash
tail -f ~/eagle_swarm_ws/log/integrated_latest/real_swarm.log
```

Expected sequence:

```text
three PX4 links healthy
→ takeoff and hover
→ randomized sector fan-out
→ RGB cue
→ thermal confirmation
→ target beacon
→ bids and task award
→ winner reaches target
→ winner lands on target
→ non-winners return home and land
→ mission complete
```

Stop cleanly:

```bash
cd ~/eagle_swarm_ws
./scripts/stop_integrated_demo.sh
```

## 4. Run fault scenarios

Start a fault-ready mission in Terminal 1:

```bash
cd ~/eagle_swarm_ws
source /opt/ros/humble/setup.bash
source install/setup.bash

AUTO_LAND=false \
OPEN_DASHBOARD=1 \
TARGET_X=10.0 \
TARGET_Y=0.0 \
COVERAGE_SEED=9001 \
./scripts/start_integrated_demo.sh
```

Run one scenario from Terminal 2:

```bash
cd ~/eagle_swarm_ws
source /opt/ros/humble/setup.bash
source install/setup.bash

./scripts/run_fault_scenario.sh coordinator_loss auto
```

Available scenarios:

```bash
./scripts/run_fault_scenario.sh coordinator_loss auto
./scripts/run_fault_scenario.sh shutdown auto
./scripts/run_fault_scenario.sh critical_battery auto
./scripts/run_fault_scenario.sh wifi_cut auto
./scripts/run_fault_scenario.sh gps_dropout auto
```

Each completed scenario produces a timestamped evidence directory containing:

```text
evidence.json
EVIDENCE.md
PASS or FAIL marker
measured recovery time
event timeline
```

View the newest coordinator-loss evidence:

```bash
latest=$(ls -dt ~/eagle_swarm_ws/evidence/runtime/coordinator_loss_* | head -n 1)
cat "$latest/EVIDENCE.md"
```

## 5. Run the complete acceptance campaign

```bash
cd ~/eagle_swarm_ws
source /opt/ros/humble/setup.bash
source install/setup.bash

SHOW_DASHBOARD=1 \
VISIBLE_PAUSE=5 \
./scripts/run_full_acceptance_campaign.sh
```

The campaign runs the normal mission, all five mandatory faults, the separation-safety scenario, and then generates a combined evidence index.

## 6. Final submission gate

```bash
cd ~/eagle_swarm_ws
source /opt/ros/humble/setup.bash
./scripts/final_submission_gate.sh
```

This performs dependency resolution, a clean build, tests, static/document validation, runtime acceptance, evidence indexing, and clean packaging.

## Key ROS 2 interfaces

```text
/swarm/heartbeat
/swarm/target_beacon
/swarm/bids
/swarm/task_award
/swarm/faults
/swarm/leader_state
/swarm/safety_events
/swarm/request_role_change
/drone/<robot_id>/go_to_target
```

Inspect interfaces:

```bash
ros2 interface show eagle_swarm_msgs/msg/Heartbeat
ros2 interface show eagle_swarm_msgs/msg/TargetBeacon
ros2 interface show eagle_swarm_msgs/msg/Bid
ros2 interface show eagle_swarm_msgs/msg/TaskAward
ros2 interface show eagle_swarm_msgs/msg/FaultEvent
ros2 interface show eagle_swarm_msgs/srv/RequestRoleChange
ros2 interface show eagle_swarm_msgs/action/GoToTarget
```

## Perception scope

The simulation validates the **perception-to-swarm interface** rather than claiming trained vision-model accuracy. RGB cueing and thermal confirmation are implemented as separate deterministic simulation stages. The target beacon is published only after confirmation and includes target identity, position, confidence, urgency, sender, battery state, and timestamp.

A real deployment would replace the deterministic perception stages with calibrated RGB and thermal inference nodes while keeping the same ROS 2 message contract.

## Safety notice

This repository is for **simulation and civilian sensing only**. SITL force-arm settings, circuit breakers, and simulated fault controls must never be copied directly to a physical aircraft without an independent safety review.

## Submission links and artifacts

- **Demonstration video:** `[ADD PRIVATE OR UNLISTED VIDEO LINK]`
- **Repository access:** private; reviewer access must be granted explicitly

- `docs/TECHNICAL_REPORT.pdf`
- `docs/architecture_diagram.pdf`
- `docs/REQUIREMENTS_TRACEABILITY.md`
- `docs/FAULT_TEST_MATRIX.md`
- `docs/DEMO_SCRIPT.md`
- `docs/TECHNICAL_DEFENSE.md`
- `docs/SAFETY_SECURITY.md`

## Candidate

**Eng. Haya Medhat Abdelhamid**  
Phase II Candidate — Senior Robotics / AI Engineer
