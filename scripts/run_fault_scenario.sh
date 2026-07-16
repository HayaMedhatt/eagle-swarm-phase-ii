#!/usr/bin/env bash
# Run one machine-checked Phase II fault scenario against an active demo.
set -Eeo pipefail

SCENARIO="${1:-}"
ROBOT="${2:-auto}"
ROS_DISTRO_NAME="${EAGLE_ROS_DISTRO:-humble}"
WS_DIR="${EAGLE_WS:-$HOME/eagle_swarm_ws}"
OUTPUT_DIR="${EVIDENCE_DIR:-$WS_DIR/evidence/runtime}"

case "$SCENARIO" in
  shutdown|coordinator_loss|wifi_cut|gps_dropout|critical_battery|separation) ;;
  *)
    echo "Usage: $0 {shutdown|coordinator_loss|wifi_cut|gps_dropout|critical_battery|separation} [robot|auto]" >&2
    exit 2
    ;;
esac

# shellcheck disable=SC1090
source "/opt/ros/${ROS_DISTRO_NAME}/setup.bash"
# shellcheck disable=SC1090
source "$WS_DIR/install/setup.bash"

if [[ ! -f "$WS_DIR/.eagle_swarm_integrated.pids" ]]; then
  echo "ERROR: integrated demo is not running." >&2
  echo "Start it with: AUTO_LAND=false OPEN_DASHBOARD=0 ./scripts/start_integrated_demo.sh" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"
exec ros2 run eagle_swarm_tools run_scenario \
  --scenario "$SCENARIO" \
  --robot "$ROBOT" \
  --output "$OUTPUT_DIR" \
  --timeout "${SCENARIO_TIMEOUT:-150}" \
  --restore-delay "${RESTORE_DELAY:-5}"
