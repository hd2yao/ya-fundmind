#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${YA_FUNDMIND_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-python}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs}"
PROVIDER="${PROVIDER:-fixture}"
ENABLE_MARKET_INTELLIGENCE="${ENABLE_MARKET_INTELLIGENCE:-false}"
DAILY_HOUR="${DAILY_HOUR:-18}"
DAILY_MINUTE="${DAILY_MINUTE:-30}"
WEEKLY_WEEKDAY="${WEEKLY_WEEKDAY:-6}"
WEEKLY_HOUR="${WEEKLY_HOUR:-10}"
WEEKLY_MINUTE="${WEEKLY_MINUTE:-0}"
DRY_RUN=false
INSTALL_DAILY=false
INSTALL_WEEKLY=false
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"

usage() {
  cat <<'USAGE'
Usage: scripts/install_launchd_scheduler.sh [--daily] [--weekly] [--dry-run]

Environment:
  PROVIDER=fixture|akshare
  ENABLE_MARKET_INTELLIGENCE=false|true
  OUTPUT_DIR=outputs
  PYTHON_BIN=python
  DAILY_HOUR=18 DAILY_MINUTE=30
  WEEKLY_WEEKDAY=6 WEEKLY_HOUR=10 WEEKLY_MINUTE=0
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --daily) INSTALL_DAILY=true ;;
    --weekly) INSTALL_WEEKLY=true ;;
    --dry-run) DRY_RUN=true ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

if [[ "${INSTALL_DAILY}" != "true" && "${INSTALL_WEEKLY}" != "true" ]]; then
  echo "nothing to install; pass --daily and/or --weekly" >&2
  exit 2
fi

if [[ ! -d "${PROJECT_DIR}" ]]; then
  echo "project directory not found: ${PROJECT_DIR}" >&2
  exit 1
fi

mkdir -p "${PROJECT_DIR}/${OUTPUT_DIR}/logs"
chmod +x "${PROJECT_DIR}/scripts/run_daily_ops.sh" "${PROJECT_DIR}/scripts/run_weekly_ops.sh"

render_plist() {
  local template="$1"
  local output="$2"
  local kind="$3"
  KIND="${kind}" \
  PROJECT_DIR="${PROJECT_DIR}" \
  PYTHON_BIN="${PYTHON_BIN}" \
  OUTPUT_DIR="${OUTPUT_DIR}" \
  PROVIDER="${PROVIDER}" \
  ENABLE_MARKET_INTELLIGENCE="${ENABLE_MARKET_INTELLIGENCE}" \
  DAILY_HOUR="${DAILY_HOUR}" \
  DAILY_MINUTE="${DAILY_MINUTE}" \
  WEEKLY_WEEKDAY="${WEEKLY_WEEKDAY}" \
  WEEKLY_HOUR="${WEEKLY_HOUR}" \
  WEEKLY_MINUTE="${WEEKLY_MINUTE}" \
  python - "$template" "$output" <<'PY'
import os
import sys
from pathlib import Path

template = Path(sys.argv[1]).read_text(encoding="utf-8")
kind = os.environ["KIND"]
hour = os.environ["DAILY_HOUR"] if kind == "daily" else os.environ["WEEKLY_HOUR"]
minute = os.environ["DAILY_MINUTE"] if kind == "daily" else os.environ["WEEKLY_MINUTE"]
text = (
    template
    .replace("${YA_FUNDMIND_PROJECT_DIR}", os.environ["PROJECT_DIR"])
    .replace("${PYTHON_BIN}", os.environ["PYTHON_BIN"])
)
text = text.replace("<string>outputs</string>", f"<string>{os.environ['OUTPUT_DIR']}</string>", 1)
text = text.replace("<string>fixture</string>", f"<string>{os.environ['PROVIDER']}</string>", 1)
text = text.replace("<string>false</string>", f"<string>{os.environ['ENABLE_MARKET_INTELLIGENCE']}</string>", 1)
if kind == "daily":
    text = text.replace("<integer>18</integer>", f"<integer>{hour}</integer>", 1)
    text = text.replace("<integer>30</integer>", f"<integer>{minute}</integer>", 1)
else:
    text = text.replace("<integer>6</integer>", f"<integer>{os.environ['WEEKLY_WEEKDAY']}</integer>", 1)
    text = text.replace("<integer>10</integer>", f"<integer>{hour}</integer>", 1)
    text = text.replace("<integer>0</integer>", f"<integer>{minute}</integer>", 1)
Path(sys.argv[2]).write_text(text, encoding="utf-8")
PY
}

install_one() {
  local kind="$1"
  local label="com.ya-fundmind.${kind}"
  local template="${PROJECT_DIR}/ops/launchd/${label}.plist.template"
  local target="${LAUNCH_AGENTS_DIR}/${label}.plist"
  local temp_target="${PROJECT_DIR}/${OUTPUT_DIR}/logs/${label}.plist.preview"

  if [[ ! -f "${template}" ]]; then
    echo "template missing: ${template}" >&2
    exit 1
  fi

  if [[ "${DRY_RUN}" == "true" ]]; then
    render_plist "${template}" "${temp_target}" "${kind}"
    if command -v plutil >/dev/null 2>&1; then
      plutil -lint "${temp_target}" >/dev/null
    fi
    echo "dry-run ${kind}: ${temp_target}"
    return
  fi

  mkdir -p "${LAUNCH_AGENTS_DIR}"
  render_plist "${template}" "${target}" "${kind}"
  if command -v plutil >/dev/null 2>&1; then
    plutil -lint "${target}" >/dev/null
  fi
  launchctl bootout "gui/$(id -u)" "${target}" >/dev/null 2>&1 || true
  if launchctl bootstrap "gui/$(id -u)" "${target}" >/dev/null 2>&1; then
    echo "installed ${kind}: ${target}"
  else
    launchctl load "${target}"
    echo "installed ${kind} with launchctl load: ${target}"
  fi
}

if [[ "${INSTALL_DAILY}" == "true" ]]; then
  install_one daily
fi
if [[ "${INSTALL_WEEKLY}" == "true" ]]; then
  install_one weekly
fi
