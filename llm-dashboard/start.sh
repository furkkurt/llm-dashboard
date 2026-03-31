#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
source .venv/bin/activate

uvicorn backend.main:app --host "${API_HOST:-127.0.0.1}" --port "${API_PORT:-8000}" &
API_PID=$!

streamlit run frontend/app.py --server.port "${STREAMLIT_PORT:-8501}"

kill "$API_PID" 2>/dev/null || true
