#!/usr/bin/env bash
# Copy the latest clean runtime evidence into a reviewer-friendly index.
set -Eeo pipefail

ROS_DISTRO_NAME="${EAGLE_ROS_DISTRO:-humble}"
WS_DIR="${EAGLE_WS:-$HOME/eagle_swarm_ws}"
NORMAL_LOG="${NORMAL_LOG:-$WS_DIR/log/integrated_latest/real_swarm.log}"
SCENARIO_ROOT="${SCENARIO_ROOT:-$WS_DIR/evidence/runtime}"
OUTPUT="${OUTPUT:-$WS_DIR/evidence/RUNTIME_EVIDENCE_INDEX.md}"

# shellcheck disable=SC1090
source "/opt/ros/${ROS_DISTRO_NAME}/setup.bash"
# shellcheck disable=SC1090
source "$WS_DIR/install/setup.bash"

[[ -f "$NORMAL_LOG" ]] || {
  echo "ERROR: normal mission log not found: $NORMAL_LOG" >&2
  exit 1
}

ros2 run eagle_swarm_tools summarize_evidence \
  --normal-log "$NORMAL_LOG" \
  --scenario-root "$SCENARIO_ROOT" \
  --output "$OUTPUT"

echo "Evidence index: $OUTPUT"
