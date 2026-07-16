# Final Submission Checklist

## Freeze the code

- [ ] Run the final revision on Ubuntu without additional live patching.
- [ ] Record the chosen `COVERAGE_SEED` and Git commit hash.
- [ ] Remove all `.before_*`, `.bak`, `.pyc`, `__pycache__`, `build/`, `install/` and temporary raw logs from the submission copy.
- [ ] Run `./scripts/preflight_submission.sh`.

## Build and test evidence

```bash
cd ~/eagle_swarm_ws
source /opt/ros/humble/setup.bash
rm -rf build install log
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install | tee evidence/final_colcon_build.log
source install/setup.bash
colcon test
colcon test-result --verbose | tee evidence/final_colcon_test.log
```

- [ ] Build finishes with no failed packages.
- [ ] All test results pass.
- [ ] Save ROS graph/interface screenshots.

## Runtime evidence

- [ ] Fresh normal mission reaches `DEMO COMPLETE`.
- [ ] Winner lands on target platform.
- [ ] Two non-winners return to their own launch points.
- [ ] Dashboard captures four bids and selected cost.
- [ ] Safety intervention/clear evidence is captured.
- [ ] Run `./scripts/run_fault_campaign.sh`.
- [ ] Run `./scripts/run_separation_acceptance.sh`.
- [ ] Run `./scripts/collect_submission_evidence.sh`.
- [ ] Confirm all five fault directories and the separation directory contain `PASS`.
- [ ] Confirm `RUNTIME_EVIDENCE_INDEX.md` says overall PASS.

## Required deliverables

- [ ] Source repository URL with readable commit history.
- [ ] Architecture diagram PDF.
- [ ] Technical report PDF no more than 20 pages.
- [ ] 15-minute demonstration video.
- [ ] README with exact local commands.
- [ ] Evidence index and fault timelines.

## Video quality

- [ ] Show Gazebo, dashboard and terminal evidence; do not rely on narration alone.
- [ ] Keep timestamps readable.
- [ ] Explain one bid calculation numerically.
- [ ] Demonstrate leader loss without stopping the full launch.
- [ ] Show critical-battery reallocation before the original winner lands.
- [ ] State limitations honestly.

## Final archive

Preferred complete gate:

```bash
cd ~/eagle_swarm_ws
./scripts/final_submission_gate.sh
```

Package only after evidence already passes:

```bash
./scripts/package_submission.sh ~/Haya_Eagle_Swarm_PhaseII_SUBMISSION.zip
```

- [ ] Verify the generated `.sha256` file.
- [ ] Extract the ZIP into a new directory and repeat the README build commands.
