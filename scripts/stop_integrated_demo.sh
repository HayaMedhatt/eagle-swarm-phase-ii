#!/usr/bin/env bash
set -eo pipefail

WS_DIR="${EAGLE_WS:-$HOME/eagle_swarm_ws}"
PX4_DIR="${PX4_DIR:-$HOME/PX4-Autopilot}"
PID_FILE="${WS_DIR}/.eagle_swarm_integrated.pids"

if [[ -f "$PID_FILE" ]]; then
  while IFS=: read -r name pid; do
    [[ -n "${name:-}" && -n "${pid:-}" ]] || continue
    if kill -0 "$pid" 2>/dev/null; then
      printf 'Stopping %-12s pid=%s\n' "$name" "$pid"
      kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    fi
  done < <(tac "$PID_FILE")
  sleep 4
  while IFS=: read -r _name pid; do
    [[ -n "${pid:-}" ]] || continue
    if kill -0 "$pid" 2>/dev/null; then
      kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
    fi
  done < <(tac "$PID_FILE")
  rm -f "$PID_FILE"
fi

pkill -TERM -f "${PX4_DIR}/build/px4_sitl_default/bin/px4" 2>/dev/null || true
pkill -TERM -f '[g]z sim' 2>/dev/null || true
pkill -TERM -f '[g]z-gui' 2>/dev/null || true
printf 'EAGLE SWARM integrated demo stopped.\n'
