#!/usr/bin/env bash
# Create a clean reviewer ZIP from the current workspace.
set -Eeo pipefail

WS_DIR="${EAGLE_WS:-$HOME/eagle_swarm_ws}"
OUTPUT_ZIP="${1:-$HOME/Haya_Eagle_Swarm_PhaseII_SUBMISSION.zip}"
STAGE="$(mktemp -d)"
cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

command -v rsync >/dev/null 2>&1 || {
  echo "ERROR: rsync is required" >&2
  exit 1
}
command -v zip >/dev/null 2>&1 || {
  echo "ERROR: zip is required" >&2
  exit 1
}

rsync -a \
  --exclude build \
  --exclude install \
  --exclude log \
  --exclude .git \
  --exclude .pytest_cache \
  --exclude __pycache__ \
  --exclude '*.pyc' \
  --exclude '*.before_*' \
  --exclude '*.bak' \
  "$WS_DIR/" "$STAGE/eagle_swarm_ws/"

EAGLE_WS="$STAGE/eagle_swarm_ws" REQUIRE_SOURCE_ONLY=1 \
  "$STAGE/eagle_swarm_ws/scripts/preflight_submission.sh"

# Defensive cleanup after validation tools.
find "$STAGE/eagle_swarm_ws" -type d \
  \( -name __pycache__ -o -name .pytest_cache \) -prune -exec rm -rf {} +
find "$STAGE/eagle_swarm_ws" -type f \
  \( -name '*.pyc' -o -name '*.before_*' -o -name '*.bak' \) -delete

rm -f "$OUTPUT_ZIP"
(
  cd "$STAGE"
  zip -qr "$OUTPUT_ZIP" eagle_swarm_ws
)
unzip -t "$OUTPUT_ZIP" >/dev/null
sha256sum "$OUTPUT_ZIP" > "$OUTPUT_ZIP.sha256"

echo "Submission ZIP: $OUTPUT_ZIP"
echo "SHA-256 file:  $OUTPUT_ZIP.sha256"
