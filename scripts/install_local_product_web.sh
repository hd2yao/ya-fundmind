#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${YA_FUNDMIND_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs}"
PORT="${PRODUCT_WEB_PORT:-8768}"
DRY_RUN=false
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
LABEL="com.ya-fundmind.web"

if [[ "${OUTPUT_DIR}" = /* ]]; then
  OUTPUT_ROOT="${OUTPUT_DIR}"
else
  OUTPUT_ROOT="${PROJECT_DIR}/${OUTPUT_DIR}"
fi

resolve_python_bin() {
  local requested="${PYTHON_BIN:-}"
  if [[ -z "${requested}" && -x "${PROJECT_DIR}/.venv/bin/python" ]]; then
    requested="${PROJECT_DIR}/.venv/bin/python"
  elif [[ -z "${requested}" ]]; then
    requested="$(command -v python3 || command -v python || true)"
  elif [[ "${requested}" != */* ]]; then
    requested="$(command -v "${requested}" || true)"
  fi
  if [[ -z "${requested}" || ! -x "${requested}" ]]; then
    echo "Python executable not found; set PYTHON_BIN to an absolute executable path" >&2
    exit 1
  fi
  printf '%s\n' "${requested}"
}

usage() {
  printf '%s\n' "Usage: scripts/install_local_product_web.sh [--dry-run]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

if [[ ! "${PORT}" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  echo "PRODUCT_WEB_PORT must be an integer between 1 and 65535" >&2
  exit 2
fi

PYTHON_BIN="$(resolve_python_bin)"
TEMPLATE="${PROJECT_DIR}/ops/launchd/${LABEL}.plist.template"
TARGET="${LAUNCH_AGENTS_DIR}/${LABEL}.plist"
PREVIEW="${OUTPUT_ROOT}/logs/${LABEL}.plist.preview"

if [[ ! -f "${TEMPLATE}" ]]; then
  echo "template missing: ${TEMPLATE}" >&2
  exit 1
fi

mkdir -p "${OUTPUT_ROOT}/logs"

render_plist() {
  local target="$1"
  PROJECT_DIR="${PROJECT_DIR}" \
  OUTPUT_ROOT="${OUTPUT_ROOT}" \
  PYTHON_BIN="${PYTHON_BIN}" \
  PORT="${PORT}" \
  "${PYTHON_BIN}" - "${TEMPLATE}" "${target}" <<'PY'
import os
import sys
from pathlib import Path
from xml.sax.saxutils import escape

replacements = {
    "${YA_FUNDMIND_PROJECT_DIR}": os.environ["PROJECT_DIR"],
    "${OUTPUT_ROOT}": os.environ["OUTPUT_ROOT"],
    "${PYTHON_BIN}": os.environ["PYTHON_BIN"],
    "${PORT}": os.environ["PORT"],
}
text = Path(sys.argv[1]).read_text(encoding="utf-8")
for placeholder, value in replacements.items():
    text = text.replace(placeholder, escape(value))
Path(sys.argv[2]).write_text(text, encoding="utf-8")
PY
}

if [[ "${DRY_RUN}" == "true" ]]; then
  render_plist "${PREVIEW}"
  if command -v plutil >/dev/null 2>&1; then
    plutil -lint "${PREVIEW}" >/dev/null
  fi
  echo "dry-run web: ${PREVIEW}"
  exit 0
fi

mkdir -p "${LAUNCH_AGENTS_DIR}"
render_plist "${TARGET}"
if command -v plutil >/dev/null 2>&1; then
  plutil -lint "${TARGET}" >/dev/null
fi
launchctl bootout "gui/$(id -u)" "${TARGET}" >/dev/null 2>&1 || true
if launchctl bootstrap "gui/$(id -u)" "${TARGET}" >/dev/null 2>&1; then
  echo "installed web: ${TARGET}"
else
  launchctl load "${TARGET}"
  echo "installed web with launchctl load: ${TARGET}"
fi
