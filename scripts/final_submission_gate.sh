#!/usr/bin/env bash
# Strict end-to-end final gate: clean build, tests, runtime evidence and package.
set -Eeo pipefail

ROS_DISTRO_NAME="${EAGLE_ROS_DISTRO:-humble}"
WS_DIR="${EAGLE_WS:-$HOME/eagle_swarm_ws}"
OUTPUT_ZIP="${1:-$HOME/Haya_Eagle_Swarm_PhaseII_SUBMISSION.zip}"

cd "$WS_DIR"
# shellcheck disable=SC1090
source "/opt/ros/${ROS_DISTRO_NAME}/setup.bash"

mkdir -p evidence
# A strict run cannot inherit stale PASS artifacts from an earlier revision.
rm -rf build install log evidence/runtime
rm -f evidence/RUNTIME_EVIDENCE_INDEX.md evidence/RUNTIME_EVIDENCE_INDEX.json

printf '\n[1/6] Dependency resolution\n'
rosdep install --from-paths src --ignore-src -r -y

printf '\n[2/6] Clean colcon build\n'
colcon build --symlink-install 2>&1 | tee evidence/final_colcon_build.log
# shellcheck disable=SC1090
source install/setup.bash

printf '\n[3/6] Colcon tests\n'
colcon test --event-handlers console_direct+ 2>&1 | tee evidence/final_colcon_test_execution.log
colcon test-result --verbose 2>&1 | tee evidence/final_colcon_test_result.log

printf '\n[4/6] Static/document preflight\n'
./scripts/preflight_submission.sh

printf '\n[5/6] Normal mission, five mandatory faults and separation safety\n'
./scripts/run_full_acceptance_campaign.sh

printf '\n[6/6] Clean source/evidence package\n'
./scripts/package_submission.sh "$OUTPUT_ZIP"

printf '\nFINAL SUBMISSION GATE PASSED\n'
printf 'Archive: %s\n' "$OUTPUT_ZIP"
printf 'Digest:  %s.sha256\n' "$OUTPUT_ZIP"
