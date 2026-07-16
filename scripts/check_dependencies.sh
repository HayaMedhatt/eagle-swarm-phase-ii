#!/usr/bin/env bash
set -eo pipefail

WS_DIR="${EAGLE_WS:-$HOME/eagle_swarm_ws}"
PX4_DIR="${PX4_DIR:-$HOME/PX4-Autopilot}"
ROS_SETUP="/opt/ros/${EAGLE_ROS_DISTRO:-humble}/setup.bash"

status=0
check_file() {
  if [[ -e "$1" ]]; then echo "OK   $1"; else echo "MISS $1"; status=1; fi
}
check_cmd() {
  if command -v "$1" >/dev/null 2>&1; then echo "OK   command $1"; else echo "MISS command $1"; status=1; fi
}

check_file "$ROS_SETUP"
check_file "$PX4_DIR/build/px4_sitl_default/bin/px4"
check_file "$WS_DIR/install/setup.bash"
check_cmd ros2
check_cmd gz
check_cmd colcon

if [[ -f "$ROS_SETUP" ]]; then
  source "$ROS_SETUP"
  [[ -f "$WS_DIR/install/setup.bash" ]] && source "$WS_DIR/install/setup.bash"
  for pkg in mavros mavros_msgs eagle_swarm_msgs eagle_swarm_common eagle_swarm_core eagle_swarm_px4 eagle_swarm_dashboard eagle_swarm_sim; do
    if ros2 pkg prefix "$pkg" >/dev/null 2>&1; then
      echo "OK   ROS package $pkg"
    else
      echo "MISS ROS package $pkg"
      status=1
    fi
  done
fi

exit "$status"
