#!/usr/bin/env bash
# Stop Streamlit + uvicorn for this dashboard and free default ports (no orphaned listeners).
set -euo pipefail

cd "$(dirname "$0")"

API_PORT="${API_PORT:-8000}"
STREAMLIT_PORT="${STREAMLIT_PORT:-8501}"

kill_port() {
  local port="$1"
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" 2>/dev/null || true
    return 0
  fi
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids=$(lsof -ti ":${port}" -sTCP:LISTEN 2>/dev/null || true)
    if [[ -n "${pids}" ]]; then
      # shellcheck disable=SC2086
      kill ${pids} 2>/dev/null || true
      sleep 0.4
      pids=$(lsof -ti ":${port}" -sTCP:LISTEN 2>/dev/null || true)
      if [[ -n "${pids}" ]]; then
        # shellcheck disable=SC2086
        kill -9 ${pids} 2>/dev/null || true
      fi
    fi
    return 0
  fi
  echo "WARN: install psmisc (fuser) or lsof to kill processes on port ${port}" >&2
  return 1
}

kill_port "$API_PORT" || true
kill_port "$STREAMLIT_PORT" || true

pkill -f "uvicorn backend.main:app" 2>/dev/null || true
pkill -f "streamlit run frontend/app.py" 2>/dev/null || true

echo "Done. Freed (best-effort) ports ${API_PORT} (API) and ${STREAMLIT_PORT} (Streamlit)."
