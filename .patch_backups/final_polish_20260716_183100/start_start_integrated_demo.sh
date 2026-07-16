#!/usr/bin/env bash
# Health-gated EAGLE SWARM PX4/Gazebo/MAVROS demo launcher.
set -Eeo pipefail

ROS_DISTRO_NAME="${EAGLE_ROS_DISTRO:-humble}"
ROS_SETUP="/opt/ros/${ROS_DISTRO_NAME}/setup.bash"
WS_DIR="${EAGLE_WS:-$HOME/eagle_swarm_ws}"
PX4_DIR="${PX4_DIR:-$HOME/PX4-Autopilot}"
PX4_BIN="${PX4_DIR}/build/px4_sitl_default/bin/px4"
TARGET_X="${TARGET_X:-10.0}"
TARGET_Y="${TARGET_Y:-0.0}"
TARGET_CUE_DELAY="${TARGET_CUE_DELAY:-2.0}"
AUTO_LAND="${AUTO_LAND:-true}"
OPEN_DASHBOARD="${OPEN_DASHBOARD:-1}"
PID_FILE="${WS_DIR}/.eagle_swarm_integrated.pids"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="${WS_DIR}/log/integrated_${RUN_ID}"
LATEST_LINK="${WS_DIR}/log/integrated_latest"
TARGET_SDF="${WS_DIR}/src/eagle_swarm_sim/models/confirmed_target/model.sdf"

fail() {
  printf '\nERROR: %s\n' "$*" >&2
  exit 1
}

need_file() {
  [[ -f "$1" ]] || fail "Required file not found: $1"
}

need_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing command: $1"
}

start_process() {
  local name="$1"
  local command="$2"
  local logfile="${LOG_DIR}/${name}.log"
  setsid bash -c "set -o pipefail; ${command}" >"$logfile" 2>&1 < /dev/null &
  local pid=$!
  printf '%s:%s\n' "$name" "$pid" >> "$PID_FILE"
  printf '  %-12s pid=%-7s log=%s\n' "$name" "$pid" "$logfile"
}

wait_for_gazebo() {
  local timeout_sec="${1:-75}"
  for ((i=1; i<=timeout_sec; i++)); do
    if gz service -l 2>/dev/null | grep -q '/world/default/control'; then
      return 0
    fi
    sleep 1
  done
  return 1
}

wait_for_fcu() {
  local topic="$1"
  local timeout_sec="${2:-90}"
  for ((i=1; i<=timeout_sec; i++)); do
    if timeout 3 ros2 topic echo "$topic" --once 2>/dev/null | grep -q 'connected: true'; then
      return 0
    fi
    sleep 1
  done
  return 1
}

spawn_target() {
  local logfile="$LOG_DIR/target_marker.log"
  : > "$logfile"
  for attempt in 1 2 3; do
    echo "Target spawn attempt $attempt" >> "$logfile"
    if gz service -s /world/default/create \
      --reqtype gz.msgs.EntityFactory \
      --reptype gz.msgs.Boolean \
      --timeout 5000 \
      --req "sdf_filename: '$TARGET_SDF', name: 'confirmed_target', pose: {position: {x: $TARGET_X, y: $TARGET_Y, z: 0.0}}" \
      >> "$logfile" 2>&1; then
      if grep -q 'data: true' "$logfile"; then
        return 0
      fi
    fi
    sleep 2
  done
  return 1
}

need_file "$ROS_SETUP"
need_file "$WS_DIR/install/setup.bash"
need_file "$PX4_BIN"
need_file "$TARGET_SDF"
need_command ros2
need_command gz
need_command setsid
need_command timeout

# Do not use nounset while sourcing ROS setup scripts.
# shellcheck disable=SC1090
source "$ROS_SETUP"
# shellcheck disable=SC1090
source "$WS_DIR/install/setup.bash"

for package in mavros eagle_swarm_common eagle_swarm_core eagle_swarm_px4 eagle_swarm_sim eagle_swarm_dashboard; do
  ros2 pkg prefix "$package" >/dev/null 2>&1 ||
    fail "ROS package '$package' is unavailable. Build/install it first."
done

if [[ -f "$PID_FILE" ]]; then
  fail "A prior integrated-demo PID file exists. Run scripts/stop_integrated_demo.sh first."
fi
if pgrep -x px4 >/dev/null 2>&1 || pgrep -f '[g]z sim' >/dev/null 2>&1; then
  fail "PX4 or Gazebo is already running. Stop the old/manual simulation first."
fi

mkdir -p "$LOG_DIR" "$WS_DIR/log"
rm -f "$LATEST_LINK"
ln -s "$LOG_DIR" "$LATEST_LINK"
: > "$PID_FILE"

GFX_ENV="export LIBGL_ALWAYS_SOFTWARE=1; export LIBGL_DRI3_DISABLE=1; export QT_QPA_PLATFORM=xcb;"
ROS_ENV="source '$ROS_SETUP'; source '$WS_DIR/install/setup.bash';"

# These commands are fed to each PX4 shell after startup. The adapter repeats
# them through MAVROS as a backup. They apply only to this unattended SITL demo.
PX4_PARAM_FEED="sleep 12; \
  echo 'param set CBRK_SUPPLY_CHK 894281'; \
  echo 'param set COM_RC_IN_MODE 4'; \
  echo 'param set COM_RCL_EXCEPT 4'; \
  echo 'param set COM_DLL_EXCEPT 4'; \
  echo 'param save'; \
  tail -f /dev/null"

printf '\nStarting health-gated EAGLE SWARM integrated demo...\n'
printf '  Workspace: %s\n  PX4:       %s\n  Logs:      %s\n\n' "$WS_DIR" "$PX4_DIR" "$LOG_DIR"

# Vehicle 0 starts Gazebo and spawns x500_0.
start_process px4_0 "$GFX_ENV cd '$PX4_DIR'; ( $PX4_PARAM_FEED ) | make px4_sitl gz_x500"
printf '\nWaiting for Gazebo world /world/default...\n'
if ! wait_for_gazebo 90; then
  tail -n 100 "$LOG_DIR/px4_0.log" >&2 || true
  "$WS_DIR/scripts/stop_integrated_demo.sh" || true
  fail "Gazebo did not become ready."
fi

# Vehicles 1 and 2 join the same Gazebo server.
start_process px4_1 "$GFX_ENV cd '$PX4_DIR'; ( $PX4_PARAM_FEED ) | PX4_GZ_STANDALONE=1 PX4_SYS_AUTOSTART=4001 PX4_GZ_MODEL=x500 PX4_GZ_MODEL_POSE='0,3,0,0,0,0' '$PX4_BIN' -i 1"
start_process px4_2 "$GFX_ENV cd '$PX4_DIR'; ( $PX4_PARAM_FEED ) | PX4_GZ_STANDALONE=1 PX4_SYS_AUTOSTART=4001 PX4_GZ_MODEL=x500 PX4_GZ_MODEL_POSE='0,-3,0,0,0,0' '$PX4_BIN' -i 2"
sleep 14

# MAVROS is an onboard controller, not a GCS. PX4's health checks need a
# GCS heartbeat before normal arming is accepted.
start_process gcs_heartbeat "python3 -u '$WS_DIR/scripts/gcs_heartbeat.py' --ports 18570 18571 18572"
sleep 4

# The visible, collision-enabled target is an acceptance-critical asset. A
# missing target used to let the logic run while producing an invalid video, so
# startup now retries and fails loudly unless Gazebo confirms creation.
printf '\nSpawning physical target platform at (%s, %s)...\n' "$TARGET_X" "$TARGET_Y"
if ! spawn_target; then
  cat "$LOG_DIR/target_marker.log" >&2 || true
  "$WS_DIR/scripts/stop_integrated_demo.sh" || true
  fail "Gazebo did not confirm creation of the physical target platform."
fi
printf '  target platform created\n'

# MAVROS bridge per PX4 instance. These exact port pairs already worked on the
# user's PX4 build.
start_process mavros_0 "$ROS_ENV ros2 launch mavros px4.launch fcu_url:=udp://:14540@127.0.0.1:14580 namespace:=uav0/mavros tgt_system:=1"
start_process mavros_1 "$ROS_ENV ros2 launch mavros px4.launch fcu_url:=udp://:14541@127.0.0.1:14581 namespace:=uav1/mavros tgt_system:=2"
start_process mavros_2 "$ROS_ENV ros2 launch mavros px4.launch fcu_url:=udp://:14542@127.0.0.1:14582 namespace:=uav2/mavros tgt_system:=3"

printf '\nWaiting for all three MAVROS/FCU links...\n'
for index in 0 1 2; do
  topic="/uav${index}/mavros/state"
  if wait_for_fcu "$topic" 100; then
    printf '  uav%s connected\n' "$index"
  else
    tail -n 100 "$LOG_DIR/mavros_${index}.log" >&2 || true
    "$WS_DIR/scripts/stop_integrated_demo.sh" || true
    fail "MAVROS uav${index} did not connect."
  fi
done

# One ROS launch starts coordinator, three real adapters, ground relay,
# safety monitor, dashboard, and the health-gated deterministic mission.
start_process real_swarm "$ROS_ENV ros2 launch eagle_swarm_core real_px4_swarm.launch.py target_x:='$TARGET_X' target_y:='$TARGET_Y' target_cue_delay_sec:='$TARGET_CUE_DELAY' auto_land:='$AUTO_LAND'"

if [[ "$OPEN_DASHBOARD" == "1" ]] && command -v xdg-open >/dev/null 2>&1; then
  (sleep 12; xdg-open http://127.0.0.1:8080 >/dev/null 2>&1 || true) &
fi

cat <<EOF

Launch passed the Gazebo and MAVROS health gates.
The ROS mission now waits until all three aerial adapters report ACTIVE.

Dashboard:
  http://127.0.0.1:8080

Follow the complete ROS mission log:
  tail -f "$LATEST_LINK/real_swarm.log"

Check arming/takeoff states:
  grep -E "pose ready|arm request|force-arm|ACTIVE|COVERAGE|SECTOR READY|RGB CUE|THERMAL|ALLOCATE|AWARD|ARRIVED|LANDED|ERROR" "$LATEST_LINK/real_swarm.log"

Run a full diagnosis:
  "$WS_DIR/scripts/diagnose_integrated_demo.sh"

Stop everything:
  "$WS_DIR/scripts/stop_integrated_demo.sh"
EOF
