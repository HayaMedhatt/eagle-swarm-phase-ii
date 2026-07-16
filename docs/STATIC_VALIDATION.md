# Static Validation Record

## Completed in the packaged revision

- Python syntax compilation across source and scripts.
- XML parsing for package manifests and SDF models.
- Bash syntax validation for every shell script.
- Fifteen pure unit tests covering:
  - explainable Contract-Net cost;
  - input clamping;
  - deterministic bid tie-break;
  - leader score and stable selection;
  - separation yielding policy;
  - reproducible randomized coverage;
  - angular/radial sector bounds;
  - minimum pairwise goal separation;
  - invalid-configuration rejection.
- GitHub Actions source-only preflight for repeatable static validation.
- PDF rendering inspection for the technical report and architecture diagram.
- ZIP integrity and source-only packaging checks.

## Runtime boundary

This packaging environment does not provide ROS 2 Humble, PX4 SITL, MAVROS or Gazebo, so it cannot execute the final runtime campaign. The candidate-machine baseline logs prove the integration path. The final source adds machine-checked fault runners so the remaining evidence is generated on Ubuntu rather than asserted in prose.

## Candidate-machine validation command

```bash
cd ~/eagle_swarm_ws
./scripts/preflight_submission.sh
source /opt/ros/humble/setup.bash
rm -rf build install log
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
colcon test
colcon test-result --verbose
```
