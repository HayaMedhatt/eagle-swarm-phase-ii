#!/usr/bin/env bash
# Run all five mandatory fault scenarios in isolated, reproducible PX4 runs.
set -Eeo pipefail

WS_DIR="${EAGLE_WS:-$HOME/eagle_swarm_ws}"
TARGET_X="${TARGET_X:-10.0}"
TARGET_Y="${TARGET_Y:-0.0}"
EVIDENCE_DIR="${EVIDENCE_DIR:-$WS_DIR/evidence/runtime}"
SCENARIOS_TEXT="${SCENARIOS:-critical_battery wifi_cut coordinator_loss shutdown gps_dropout}"
read -r -a SCENARIOS_ARRAY <<< "$SCENARIOS_TEXT"
VISIBLE_PAUSE="${VISIBLE_PAUSE:-3}"

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

total_scenarios="${#SCENARIOS_ARRAY[@]}"
scenario_index=0
for scenario in "${SCENARIOS_ARRAY[@]}"; do
  scenario_index=$((scenario_index + 1))
  pretty_name="${scenario//_/ }"
  echo
  echo "============================================================"
  printf 'FAULT %s/%s: %s\n' "$scenario_index" "$total_scenarios" "${pretty_name^^}"
  echo "Watch the open Digital Twin: fleet health and latest fault update live."
  echo "============================================================"
  cleanup
  sleep 4

  seed="$(scenario_seed "$scenario")"
  TARGET_X="$TARGET_X" TARGET_Y="$TARGET_Y" \
  COVERAGE_SEED="$seed" AUTO_LAND=false OPEN_DASHBOARD=0 \
    "$WS_DIR/scripts/start_integrated_demo.sh"

  # The scenario runner waits for the exact readiness condition, injects the
  # fault, checks recovery, and writes measured evidence.
  EVIDENCE_DIR="$EVIDENCE_DIR" \
    "$WS_DIR/scripts/run_fault_scenario.sh" "$scenario" auto

  latest_evidence="$(find "$EVIDENCE_DIR" -maxdepth 1 -type d -name "${scenario}_*" \
    -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-)"
  if [[ -n "$latest_evidence" && -f "$latest_evidence/EVIDENCE.md" ]]; then
    echo
    echo "Scenario evidence summary:"
    grep -E '^[*][*](Result|Target robot|Scenario duration|Measured recovery|Reason):' \
      "$latest_evidence/EVIDENCE.md" || true
  fi

  sleep "$VISIBLE_PAUSE"
  cleanup
  sleep 5
done

echo
echo "Fault campaign complete. Evidence root: $EVIDENCE_DIR"
