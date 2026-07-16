#!/usr/bin/env bash
# One command: normal mission + five mandatory faults + scored separation.
set -Eeo pipefail

WS_DIR="${EAGLE_WS:-$HOME/eagle_swarm_ws}"
RUNTIME_ROOT="${EVIDENCE_DIR:-$WS_DIR/evidence/runtime}"
TARGET_X="${TARGET_X:-10.0}"
TARGET_Y="${TARGET_Y:-0.0}"
NORMAL_SEED="${NORMAL_SEED:-2180021560}"
NORMAL_TIMEOUT="${NORMAL_TIMEOUT:-210}"
SHOW_DASHBOARD="${SHOW_DASHBOARD:-1}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
CAMPAIGN_DIR="${CAMPAIGN_DIR:-$RUNTIME_ROOT/campaign_$STAMP}"
NORMAL_DIR="$CAMPAIGN_DIR/normal"
SCENARIO_DIR="$CAMPAIGN_DIR/scenarios"
CAMPAIGN_INDEX="$CAMPAIGN_DIR/RUNTIME_EVIDENCE_INDEX.md"

cleanup() {
  "$WS_DIR/scripts/stop_integrated_demo.sh" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

mkdir -p "$NORMAL_DIR" "$SCENARIO_DIR"
cleanup
sleep 4

echo "Starting final normal acceptance run..."
TARGET_X="$TARGET_X" TARGET_Y="$TARGET_Y" COVERAGE_SEED="$NORMAL_SEED" \
AUTO_LAND=true OPEN_DASHBOARD="$SHOW_DASHBOARD" \
  "$WS_DIR/scripts/start_integrated_demo.sh"

normal_log="$WS_DIR/log/integrated_latest/real_swarm.log"
passed=0
for ((second=1; second<=NORMAL_TIMEOUT; second++)); do
  if [[ -f "$normal_log" ]] && grep -q 'DEMO COMPLETE' "$normal_log"; then
    passed=1
    break
  fi
  sleep 1
done

if [[ "$passed" != "1" ]]; then
  cp -a "$WS_DIR/log/integrated_latest/." "$NORMAL_DIR/" 2>/dev/null || true
  echo "FAIL: normal mission did not reach DEMO COMPLETE within ${NORMAL_TIMEOUT}s" > "$NORMAL_DIR/FAIL"
  exit 1
fi

cp -a "$WS_DIR/log/integrated_latest/." "$NORMAL_DIR/"
echo "Normal mission reached DEMO COMPLETE" > "$NORMAL_DIR/PASS"
cleanup
sleep 5

echo "Starting five-scenario fault campaign..."
SCENARIOS="critical_battery wifi_cut coordinator_loss shutdown gps_dropout" \
EVIDENCE_DIR="$SCENARIO_DIR" \
TARGET_X="$TARGET_X" TARGET_Y="$TARGET_Y" \
  "$WS_DIR/scripts/run_fault_campaign.sh"

echo "Starting scored separation-safety acceptance..."
EVIDENCE_DIR="$SCENARIO_DIR" \
TARGET_X="$TARGET_X" TARGET_Y="$TARGET_Y" \
  "$WS_DIR/scripts/run_separation_acceptance.sh"

NORMAL_LOG="$NORMAL_DIR/real_swarm.log" \
SCENARIO_ROOT="$SCENARIO_DIR" \
OUTPUT="$CAMPAIGN_INDEX" \
  "$WS_DIR/scripts/collect_submission_evidence.sh"

if ! grep -q 'Overall acceptance evidence: PASS' "$CAMPAIGN_INDEX"; then
  echo "ERROR: evidence index is incomplete." >&2
  exit 1
fi

# Publish one stable reviewer path while preserving the immutable campaign.
cp "$CAMPAIGN_INDEX" "$WS_DIR/evidence/RUNTIME_EVIDENCE_INDEX.md"
cp "${CAMPAIGN_INDEX%.md}.json" "$WS_DIR/evidence/RUNTIME_EVIDENCE_INDEX.json"

echo
echo "FULL ACCEPTANCE CAMPAIGN PASSED"
echo "Campaign:      $CAMPAIGN_DIR"
echo "Evidence index: $WS_DIR/evidence/RUNTIME_EVIDENCE_INDEX.md"
