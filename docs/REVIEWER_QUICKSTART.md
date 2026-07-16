# Reviewer Quick Start

## Clean build

```bash
cd ~/eagle_swarm_ws
source /opt/ros/humble/setup.bash
rm -rf build install log
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
colcon test
colcon test-result --verbose
```

## Normal mission

```bash
COVERAGE_SEED=2180021560 ./scripts/start_integrated_demo.sh
```

Open `http://127.0.0.1:8080` and follow:

```bash
tail -f log/integrated_latest/real_swarm.log
```

Expected final marker:

```text
DEMO COMPLETE
```

## Full machine-checked acceptance campaign

```bash
./scripts/run_full_acceptance_campaign.sh
```

Confirm:

```bash
grep 'Overall acceptance evidence: PASS' evidence/RUNTIME_EVIDENCE_INDEX.md
find evidence/runtime -path '*/scenarios/*/PASS' -print
```

The full campaign writes a new timestamped directory; it does not reuse old scenario artifacts.

## Strict final gate

```bash
./scripts/final_submission_gate.sh
```

The gate fails on build/test errors, a missing normal milestone, any failed fault scenario, missing documentation or packaging contamination.
