#!/usr/bin/env bash
# Installs venv + deps + dirs only. Does not read, create, rename, or delete any secrets file.
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f backend/main.py ]; then
  echo "ERROR: Run setup.sh from the dashboard project root (expected backend/main.py here)." >&2
  echo "       Current directory: $(pwd)" >&2
  exit 1
fi

echo "Setup directory (project root): $(pwd)"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
mkdir -p tools results results/exports results/raw-logs temp/runs

if [ ! -f tools/detekt-cli.jar ]; then
  echo "Download detekt-cli.jar manually into tools/ (see https://github.com/detekt/detekt/releases)"
fi

echo "Setup complete. Activate with: source .venv/bin/activate"
