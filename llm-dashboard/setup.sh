#!/usr/bin/env bash
# Installs venv + deps + dirs + Kotlin JVM compiler (tools/kotlin). Does not read, create, rename, or delete any secrets file.
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
mkdir -p tools results results/exports results/raw-logs temp/runs scripts

# --- Kotlin JVM compiler (kotlinc) for analyze Kotlin path ---
KOTLIN_VERSION="${KOTLIN_VERSION:-2.1.10}"
KOTLIN_ZIP_NAME="kotlin-compiler-${KOTLIN_VERSION}.zip"
KOTLIN_URL="https://github.com/JetBrains/kotlin/releases/download/v${KOTLIN_VERSION}/${KOTLIN_ZIP_NAME}"
KOTLIN_INSTALL_DIR="$(pwd)/tools/kotlin"
KOTLIN_KOTLINC="${KOTLIN_INSTALL_DIR}/bin/kotlinc"

if [ ! -f "$KOTLIN_KOTLINC" ]; then
  echo "Installing Kotlin compiler ${KOTLIN_VERSION} into tools/kotlin ..."
  command -v curl >/dev/null 2>&1 || {
    echo "ERROR: curl is required to download the Kotlin compiler." >&2
    exit 1
  }
  command -v unzip >/dev/null 2>&1 || {
    echo "ERROR: unzip is required to extract the Kotlin compiler." >&2
    exit 1
  }
  TMPDIR=$(mktemp -d)
  cleanup() { rm -rf "$TMPDIR"; }
  trap cleanup EXIT
  curl -fL --retry 3 --retry-delay 2 -o "${TMPDIR}/kotlin.zip" "$KOTLIN_URL"
  mkdir -p "${TMPDIR}/extract"
  unzip -q "${TMPDIR}/kotlin.zip" -d "${TMPDIR}/extract"
  shopt -s nullglob
  inner=( "${TMPDIR}/extract"/* )
  shopt -u nullglob
  if [ "${#inner[@]}" -ne 1 ] || [ ! -d "${inner[0]}" ] || [ ! -f "${inner[0]}/bin/kotlinc" ]; then
    echo "ERROR: Unexpected Kotlin zip layout under ${TMPDIR}/extract (expected one root dir with bin/kotlinc)." >&2
    exit 1
  fi
  rm -rf "$KOTLIN_INSTALL_DIR"
  mkdir -p "$(dirname "$KOTLIN_INSTALL_DIR")"
  mv "${inner[0]}" "$KOTLIN_INSTALL_DIR"
  echo "Kotlin compiler installed: $KOTLIN_KOTLINC"
else
  echo "Kotlin compiler already present: $KOTLIN_KOTLINC"
fi

if ! command -v java >/dev/null 2>&1; then
  echo "WARNING: No java on PATH. Install JDK 17+ (or 21 LTS); kotlinc needs it to compile Kotlin."
fi

if [ ! -f tools/detekt-cli.jar ]; then
  echo "Download detekt-cli.jar manually into tools/ (see https://github.com/detekt/detekt/releases)"
fi

echo "Setup complete. Activate with: source .venv/bin/activate"
