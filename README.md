# EAGLE SWARM

A reproducible **ROS 2 + PX4 SITL + Gazebo** prototype for a three-UAV civilian reconnaissance swarm. The system demonstrates distributed coordination, constrained-random coverage, Contract-Net task allocation, leader election, battery-aware return-to-base, collision-safety behavior, fault injection, a Ground Relay extension, and a browser-based Digital Twin.

> **Public repository scope:** This repository contains the runnable source code and setup instructions.

## Demonstrated capabilities

- Three independent PX4 SITL x500 vehicles operating in one Gazebo environment.
- Health-gated startup for Gazebo, PX4, MAVROS, and the ROS 2 swarm graph.
- Constrained randomized coverage movement with a logged reproducibility seed.
- Deterministic RGB cue followed by simulated thermal confirmation.
- ROS 2 communication through heartbeat, target-beacon, bid, award, leader, fault, and safety interfaces.
- Explainable Contract-Net cost:

  ```text
  distance + battery_penalty + role_penalty + link_quality_penalty
  ```

- Replicated coordinator logic and heartbeat-based leader election.
- The winning UAV lands on the physical target platform.
- Non-winning UAVs return to their individual launch positions and land.
- Virtual battery depletion, critical-battery RTB, task release, and re-auction.
- Active separation intervention with hold/resume hysteresis and near-miss logging.
- Ground Relay participation through the same heartbeat, bid, award, and election contracts.
- Automated fault-scenario execution with measured recovery times.
- Browser-based Digital Twin for live operational visibility.

## Supported environment

- Ubuntu 22.04 LTS
- ROS 2 Humble
- Python 3.10+
- PX4-Autopilot SITL at `~/PX4-Autopilot`
- Gazebo Sim compatible with the PX4 checkout
- MAVROS and MAVROS Extras
- Git

## Repository architecture

```text
eagle_swarm_ws/
├── .github/
│   └── workflows/
│       └── static-validation.yml
├── scripts/
│   ├── start_integrated_demo.sh
│   ├── stop_integrated_demo.sh
│   ├── run_fault_scenario.sh
│   ├── run_fault_campaign.sh
│   ├── run_full_acceptance_campaign.sh
│   ├── run_separation_acceptance.sh
│   ├── collect_submission_evidence.sh
│   ├── diagnose_integrated_demo.sh
│   ├── build_workspace.sh
│   ├── check_dependencies.sh
│   ├── preflight_submission.sh
│   ├── final_submission_gate.sh
│   └── package_submission.sh
├── src/
│   ├── eagle_swarm_common/         # reusable policies and unit tests
│   ├── eagle_swarm_msgs/           # custom messages, service, and action
│   ├── eagle_swarm_core/           # mission, agents, auction, leader election
│   ├── eagle_swarm_px4/            # PX4/MAVROS adapters and onboard safety
│   ├── eagle_swarm_sim/            # Gazebo assets and separation monitor
│   ├── eagle_swarm_dashboard/      # browser and terminal Digital Twin
│   └── eagle_swarm_tools/          # fault injection and scenario verification
├── .gitignore
├── README.md
└── requirements-dev.txt
```

The following directories are generated locally and should not be committed:

```text
build/
install/
log/
evidence/runtime/
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
| `eagle_swarm_tools` | Fault injector, automated scenario runner, and recovery verification |

## 1. Clone the repository

```bash
cd ~
git clone <REPOSITORY_URL> eagle_swarm_ws
cd ~/eagle_swarm_ws
```

Replace `<REPOSITORY_URL>` with the public GitHub repository URL.

## 2. Install dependencies

Initialize `rosdep` once on a new machine:

```bash
sudo rosdep init
rosdep update
```

If `rosdep` is already initialized, run only:

```bash
rosdep update
```

Install project dependencies:

```bash
cd ~/eagle_swarm_ws
source /opt/ros/humble/setup.bash

rosdep install --from-paths src --ignore-src -r -y
sudo apt install -y python3-pytest
```

PX4-Autopilot must be available at:

```text
~/PX4-Autopilot
```

## 3. Build the workspace

```bash
cd ~/eagle_swarm_ws
source /opt/ros/humble/setup.bash

rm -rf build install log
colcon build --symlink-install
source install/setup.bash
```

## 4. Run tests

Run ROS package tests:

```bash
cd ~/eagle_swarm_ws
source /opt/ros/humble/setup.bash
source install/setup.bash

colcon test
colcon test-result --verbose
```

Run the policy, coverage, and evidence-report tests directly:

```bash
cd ~/eagle_swarm_ws

PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=src/eagle_swarm_common:src/eagle_swarm_tools \
python3 -m pytest -q -p no:cacheprovider \
  src/eagle_swarm_common/test/test_policy.py \
  src/eagle_swarm_common/test/test_coverage.py \
  src/eagle_swarm_tools/test/test_evidence_report.py
```

## 5. Run the normal integrated mission

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

Open the Digital Twin at:

```text
http://127.0.0.1:8080
```

Follow the mission log:

```bash
tail -f ~/eagle_swarm_ws/log/integrated_latest/real_swarm.log
```

Expected mission sequence:

```text
three PX4 links healthy
→ takeoff and hover
→ constrained-random sector fan-out
→ RGB cue
→ thermal confirmation
→ target beacon
→ Contract-Net bids and task award
→ winner reaches and lands on the target
→ non-winners return home and land
→ mission complete
```

Stop the simulation cleanly:

```bash
cd ~/eagle_swarm_ws
./scripts/stop_integrated_demo.sh
```

## 6. Run individual fault scenarios

For an isolated fault test, start a fault-ready mission in **Terminal 1**:

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

Run one scenario from **Terminal 2**:

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

`auto` selects the appropriate active leader or task winner for the requested scenario.

Fault tests may also be executed with `AUTO_LAND=true` when a complete recovery-and-landing demonstration is desired. Start the scenario runner early so it can inject the fault before the normal mission completes.

Generated scenario results are written locally under:

```text
evidence/runtime/
```

These generated artifacts are not stored in the public repository.

## 7. Run the complete acceptance campaign

```bash
cd ~/eagle_swarm_ws
source /opt/ros/humble/setup.bash
source install/setup.bash

SHOW_DASHBOARD=1 \
VISIBLE_PAUSE=5 \
./scripts/run_full_acceptance_campaign.sh
```

The campaign executes:

1. The normal integrated mission.
2. Coordinator loss.
3. Drone shutdown.
4. Critical battery.
5. Virtual Wi-Fi cut.
6. GPS dropout.
7. Separation-safety acceptance.

A combined local evidence index is generated after the campaign.

## Key ROS 2 interfaces

```text
/swarm/heartbeat
/swarm/target_beacon
/swarm/bids
/swarm/task_award
/swarm/leader
/swarm/faults
/swarm/safety_events
/swarm/mission_command
/swarm/request_role_change
/drone/<robot_id>/go_to_target
```

Inspect the custom interfaces:

```bash
ros2 interface show eagle_swarm_msgs/msg/Heartbeat
ros2 interface show eagle_swarm_msgs/msg/TargetBeacon
ros2 interface show eagle_swarm_msgs/msg/Bid
ros2 interface show eagle_swarm_msgs/msg/TaskAward
ros2 interface show eagle_swarm_msgs/msg/FaultEvent
ros2 interface show eagle_swarm_msgs/srv/RequestRoleChange
ros2 interface show eagle_swarm_msgs/action/GoToTarget
```

## Configuration variables

| Variable | Purpose | Example |
|---|---|---|
| `AUTO_LAND` | Enables the normal final landing sequence | `true` |
| `OPEN_DASHBOARD` | Opens the browser Digital Twin | `1` |
| `TARGET_X` | Target X coordinate | `10.0` |
| `TARGET_Y` | Target Y coordinate | `0.0` |
| `COVERAGE_SEED` | Reproduces a constrained-random coverage pattern | `9003` |
| `SHOW_DASHBOARD` | Displays the dashboard during campaigns | `1` |
| `VISIBLE_PAUSE` | Pause between visible campaign scenarios | `5` |



## Author

**Eng. Haya Medhat Abdelhamid**

Robotics and Artificial Intelligence Engineer
