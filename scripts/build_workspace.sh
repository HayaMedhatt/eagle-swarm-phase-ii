#!/usr/bin/env bash
set -Eeo pipefail

WS_DIR="${EAGLE_WS:-$HOME/eagle_swarm_ws}"
ROS_SETUP="/opt/ros/${EAGLE_ROS_DISTRO:-humble}/setup.bash"

[[ -f "$ROS_SETUP" ]] || { echo "Missing $ROS_SETUP" >&2; exit 1; }
cd "$WS_DIR"
source "$ROS_SETUP"
rm -rf build install log
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash

echo
ros2 pkg prefix eagle_swarm_common
ros2 pkg prefix eagle_swarm_px4
ros2 pkg prefix eagle_swarm_core
ros2 pkg prefix eagle_swarm_dashboard
echo "Build complete."
