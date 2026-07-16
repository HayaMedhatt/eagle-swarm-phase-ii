#!/usr/bin/env bash
# Prove active 3-D separation intervention and hysteretic release in fresh SITL.
set -Eeo pipefail

WS_DIR="${EAGLE_WS:-$HOME/eagle_swarm_ws}"
EVIDENCE_DIR="${EVIDENCE_DIR:-$WS_DIR/evidence/runtime}"
TARGET_X="${TARGET_X:-10.0}"
TARGET_Y="${TARGET_Y:-0.0}"

cleanup() {
  "$WS_DIR/scripts/stop_integrated_demo.sh" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

cleanup
sleep 4

# Delay target cueing so the safety crossing test owns the mission goals.
TARGET_X="$TARGET_X" TARGET_Y="$TARGET_Y" \
COVERAGE_SEED="${SEPARATION_SEED:-9010}" \
TARGET_CUE_DELAY=300 AUTO_LAND=false OPEN_DASHBOARD=0 \
  "$WS_DIR/scripts/start_integrated_demo.sh"

EVIDENCE_DIR="$EVIDENCE_DIR" \
  "$WS_DIR/scripts/run_fault_scenario.sh" separation auto

cleanup
sleep 4

echo "Separation acceptance complete. Evidence root: $EVIDENCE_DIR"
