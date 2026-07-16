#!/usr/bin/env bash
# Strict offline/ROS-aware submission preflight. Exits non-zero on any gap.
set -Eeo pipefail

WS_DIR="${EAGLE_WS:-$HOME/eagle_swarm_ws}"
cd "$WS_DIR"

failures=0
pass() { printf 'PASS  %s\n' "$*"; }
fail() { printf 'FAIL  %s\n' "$*" >&2; failures=$((failures + 1)); }

if find src -type f \( -name '*.before_*' -o -name '*.bak' -o -name '*.pyc' \) | grep -q .; then
  fail "temporary backup/bytecode files remain under src"
else
  pass "source tree contains no temporary patch artifacts"
fi

if [[ -d build || -d install || -d log ]]; then
  if [[ "${REQUIRE_SOURCE_ONLY:-0}" == "1" ]]; then
    fail "build/install/log directories are present in source-only staging"
  else
    echo "INFO  build/install/log may exist in the working workspace; package script excludes them"
  fi
else
  pass "workspace is source-only"
fi

if [[ -f .eagle_swarm_integrated.pids ]]; then
  fail "stale integrated-demo PID file remains"
else
  pass "no stale integrated-demo PID file"
fi

if python3 - <<'PY'
from pathlib import Path
for root in (Path('src'), Path('scripts')):
    for path in root.rglob('*.py'):
        compile(path.read_text(), str(path), 'exec')
print('validated Python source without writing bytecode')
PY
then
  pass "Python syntax compilation"
else
  fail "Python syntax compilation"
fi

if python3 - <<'PY'
from pathlib import Path
from xml.etree import ElementTree
for path in Path('src').rglob('package.xml'):
    ElementTree.parse(path)
for path in Path('src').rglob('*.sdf'):
    ElementTree.parse(path)
print('validated XML/SDF')
PY
then
  pass "package.xml and SDF parsing"
else
  fail "package.xml or SDF parsing"
fi

if PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=src/eagle_swarm_common:src/eagle_swarm_tools \
  python3 -m pytest -q -p no:cacheprovider \
  src/eagle_swarm_common/test/test_policy.py \
  src/eagle_swarm_common/test/test_coverage.py \
  src/eagle_swarm_tools/test/test_evidence_report.py; then
  pass "pure policy, coverage and evidence unit tests"
else
  fail "pure policy, coverage and evidence unit tests"
fi

for script in scripts/*.sh; do
  if bash -n "$script"; then
    pass "bash syntax: $script"
  else
    fail "bash syntax: $script"
  fi
done

required=(
  README.md
  docs/TECHNICAL_REPORT.pdf
  docs/architecture_diagram.pdf
  docs/REQUIREMENTS_TRACEABILITY.md
  docs/FAULT_TEST_MATRIX.md
  docs/DEMO_SCRIPT.md
  docs/TECHNICAL_DEFENSE.md
  docs/SAFETY_SECURITY.md
  docs/ASSESSMENT_SCORECARD.md
  docs/SUBMISSION_MANIFEST.md
  docs/REVIEWER_QUICKSTART.md
  docs/FINAL_CHANGELOG.md
  docs/FINAL_HANDOFF.md
)
for artifact in "${required[@]}"; do
  [[ -s "$artifact" ]] && pass "artifact: $artifact" || fail "missing artifact: $artifact"
done

if command -v pdfinfo >/dev/null 2>&1; then
  report_pages="$(pdfinfo docs/TECHNICAL_REPORT.pdf 2>/dev/null | awk '/^Pages:/ {print $2}')"
  if [[ "$report_pages" =~ ^[0-9]+$ ]] && (( report_pages <= 20 )); then
    pass "technical report page limit (${report_pages}/20)"
  else
    fail "technical report exceeds or cannot prove 20-page limit"
  fi
fi

if command -v colcon >/dev/null 2>&1 && [[ -f /opt/ros/humble/setup.bash ]]; then
  echo "ROS/colcon detected. Run the clean build separately before packaging:"
  echo "  rm -rf build install log && colcon build --symlink-install && colcon test"
else
  echo "INFO  ROS/colcon runtime not detected; offline preflight only."
fi

if (( failures > 0 )); then
  echo "Preflight failed with $failures issue(s)." >&2
  exit 1
fi

echo "Submission preflight passed."
