#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${YA_FUNDMIND_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs}"
PORT="${PRODUCT_WEB_PORT:-8768}"
LABEL="com.ya-fundmind.web"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"

resolve_python_bin() {
  local requested="${PYTHON_BIN:-}"
  if [[ -z "${requested}" && -x "${PROJECT_DIR}/.venv/bin/python" ]]; then
    requested="${PROJECT_DIR}/.venv/bin/python"
  elif [[ -z "${requested}" ]]; then
    requested="$(command -v python3 || command -v python || true)"
  fi
  if [[ -z "${requested}" || ! -x "${requested}" ]]; then
    echo "Python executable not found; set PYTHON_BIN" >&2
    exit 1
  fi
  printf '%s\n' "${requested}"
}

PYTHON_BIN="$(resolve_python_bin)"

cd "${PROJECT_DIR}/web"
npm ci
npm run typecheck
npm test -- --run
npm run build

cd "${PROJECT_DIR}"
"${PYTHON_BIN}" -m fund_agent.cli product-web \
  --output-dir "${OUTPUT_DIR}" \
  --host 127.0.0.1 \
  --port "${PORT}" \
  --dry-run

if [[ -f "${PLIST}" ]]; then
  launchctl kickstart -k "gui/$(id -u)/${LABEL}"
  sleep 2
  OUTPUT_DIR="${OUTPUT_DIR}" PRODUCT_WEB_PORT="${PORT}" bash scripts/status_local_product_web.sh
else
  echo "web build verified; install the local service with: bash scripts/install_local_product_web.sh"
fi
