#!/usr/bin/env bash
# Run all five mandatory fault scenarios in isolated, reproducible PX4 runs.
set -Eeo pipefail

WS_DIR="${EAGLE_WS:-$HOME/eagle_swarm_ws}"
TARGET_X="${TARGET_X:-10.0}"
TARGET_Y="${TARGET_Y:-0.0}"
EVIDENCE_DIR="${EVIDENCE_DIR:-$WS_DIR/evidence/runtime}"
SCENARIOS_TEXT="${SCENARIOS:-coordinator_loss shutdown critical_battery wifi_cut gps_dropout}"
read -r -a SCENARIOS_ARRAY <<< "$SCENARIOS_TEXT"

mkdir -p "$EVIDENCE_DIR"

cleanup() {
  "$WS_DIR/scripts/stop_integrated_demo.sh" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

scenario_seed() {
  case "$1" in
    coordinator_loss) echo 9001 ;;
    shutdown) echo 9002 ;;
    critical_battery) echo 9003 ;;
    wifi_cut) echo 9004 ;;
    gps_dropout) echo 9005 ;;
  esac
}

for scenario in "${SCENARIOS_ARRAY[@]}"; do
  echo
  echo "============================================================"
  echo "FAULT CAMPAIGN: $scenario"
  echo "============================================================"
  cleanup
  sleep 4

  seed="$(scenario_seed "$scenario")"
  TARGET_X="$TARGET_X" TARGET_Y="$TARGET_Y" \
  COVERAGE_SEED="$seed" AUTO_LAND=false OPEN_DASHBOARD=0 \
    "$WS_DIR/scripts/start_integrated_demo.sh"

  # The scenario runner itself waits for the exact ready condition: leader,
  # active robot, or first task award.  No fragile fixed mission delay is used.
  EVIDENCE_DIR="$EVIDENCE_DIR" \
    "$WS_DIR/scripts/run_fault_scenario.sh" "$scenario" auto

  cleanup
  sleep 5
done

echo
echo "Fault campaign complete. Evidence root: $EVIDENCE_DIR"
