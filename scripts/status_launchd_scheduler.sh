#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${YA_FUNDMIND_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-python}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs}"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"

cd "${PROJECT_DIR}"

status_one() {
  local kind="$1"
  local label="com.ya-fundmind.${kind}"
  local plist="${LAUNCH_AGENTS_DIR}/${label}.plist"
  local installed="false"
  local loaded="false"
  [[ -f "${plist}" ]] && installed="true"
  if launchctl print "gui/$(id -u)/${label}" >/dev/null 2>&1; then
    loaded="true"
  fi
  echo "${kind} 是否已安装: ${installed}"
  echo "${kind} launchctl 是否加载: ${loaded}"
  echo "${kind} plist 路径: ${plist}"
  echo "${kind} 最近日志路径: ${PROJECT_DIR}/${OUTPUT_DIR}/logs/${kind}-ops-$(date +%F).log"
}

echo "daily 是否已安装 / weekly 是否已安装"
status_one daily
status_one weekly

"${PYTHON_BIN}" -m fund_agent.cli ops-status \
  --output-dir "${OUTPUT_DIR}" \
  --json-output "${OUTPUT_DIR}/ops_status.json" \
  --write-latest-summary

echo "latest_run: $(python - "${OUTPUT_DIR}" <<'PY'
import json
import sys
from pathlib import Path
p = Path(sys.argv[1]) / "ops_status.json"
if p.exists():
    data = json.loads(p.read_text())
    print((data.get("latest_run") or {}).get("as_of") or "--")
else:
    print("--")
PY
)"
echo "latest_summary exists: $([[ -f "${OUTPUT_DIR}/latest_summary.md" ]] && echo true || echo false)"
echo "ops_status exists: $([[ -f "${OUTPUT_DIR}/ops_status.json" ]] && echo true || echo false)"
echo "dashboard exists: $([[ -f "${OUTPUT_DIR}/dashboard/index.html" ]] && echo true || echo false)"
