#!/usr/bin/env bash
# This script does not modify an existing .env file. Put API keys in .env only (not .env.example).
set -euo pipefail

cd "$(dirname "$0")"

echo "Note: This script does not overwrite .env — edit .env manually for API keys."

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
mkdir -p tools results results/exports results/raw-logs temp/runs

if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo "Created .env from .env.example — add your API keys and paths."
fi

if [ ! -f tools/detekt-cli.jar ]; then
  echo "Download detekt-cli.jar manually into tools/ (see https://github.com/detekt/detekt/releases)"
fi

echo "Setup complete. Activate with: source .venv/bin/activate"
