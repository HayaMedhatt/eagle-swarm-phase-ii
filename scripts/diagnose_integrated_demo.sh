#!/usr/bin/env bash
set -eo pipefail

ROS_SETUP="/opt/ros/${EAGLE_ROS_DISTRO:-humble}/setup.bash"
WS_DIR="${EAGLE_WS:-$HOME/eagle_swarm_ws}"
LOG_DIR="${WS_DIR}/log/integrated_latest"

source "$ROS_SETUP"
source "$WS_DIR/install/setup.bash"

echo '=== Processes ==='
pgrep -af 'px4|gz sim|mavros|px4_adapter|mission_demo|swarm_coordinator' || true

echo
echo '=== MAVROS states ==='
for i in 0 1 2; do
  echo "--- uav$i ---"
  timeout 4 ros2 topic echo "/uav$i/mavros/state" --once 2>/dev/null || echo 'NO STATE MESSAGE'
done

echo
echo '=== Latest ROS mission milestones ==='
if [[ -f "$LOG_DIR/real_swarm.log" ]]; then
  grep -E 'FCU connected|pose ready|arm request|force-arm|ACTIVE|COVERAGE|SECTOR READY|RGB CUE|THERMAL|BID\(real\)|ALLOCATE|AWARD\(real\)|ARRIVED|REASSIGN|RECOVER|RTB|LAND|ERROR|WARN' "$LOG_DIR/real_swarm.log" | tail -n 180 || true
else
  echo "No integrated log at $LOG_DIR"
fi

echo
echo '=== PX4 preflight / arming errors ==='
grep -EHi 'preflight|arming|denied|power unavailable|fail|error' "$LOG_DIR"/px4_*.log 2>/dev/null | tail -n 120 || true

echo
echo '=== Dashboard ==='
echo 'http://127.0.0.1:8080'

echo
echo '=== GCS heartbeat ==='
if [[ -f "$LOG_DIR/gcs_heartbeat.log" ]]; then
  tail -n 20 "$LOG_DIR/gcs_heartbeat.log"
else
  echo 'NO GCS HEARTBEAT LOG'
fi
