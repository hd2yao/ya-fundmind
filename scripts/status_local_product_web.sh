#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${YA_FUNDMIND_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs}"
PORT="${PRODUCT_WEB_PORT:-8768}"
DEFAULT_URL="http://127.0.0.1:8768"
LABEL="com.ya-fundmind.web"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"

if [[ "${OUTPUT_DIR}" = /* ]]; then
  OUTPUT_ROOT="${OUTPUT_DIR}"
else
  OUTPUT_ROOT="${PROJECT_DIR}/${OUTPUT_DIR}"
fi

installed=false
loaded=false
health_reachable=false
home_reachable=false
[[ -f "${PLIST}" ]] && installed=true
if launchctl print "gui/$(id -u)/${LABEL}" >/dev/null 2>&1; then
  loaded=true
fi
if command -v curl >/dev/null 2>&1; then
  curl --fail --silent --show-error --max-time 3 "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1 && health_reachable=true
  curl --fail --silent --show-error --max-time 3 "http://127.0.0.1:${PORT}/" >/dev/null 2>&1 && home_reachable=true
fi

echo "web installed: ${installed}"
echo "web launchctl loaded: ${loaded}"
echo "web health reachable: ${health_reachable}"
echo "web home reachable: ${home_reachable}"
echo "web url: http://127.0.0.1:${PORT}"
echo "web default url: ${DEFAULT_URL}"
echo "web plist: ${PLIST}"
echo "web stdout log: ${OUTPUT_ROOT}/logs/product-web.out.log"
echo "web stderr log: ${OUTPUT_ROOT}/logs/product-web.err.log"

if [[ "${installed}" != "true" || "${loaded}" != "true" || "${health_reachable}" != "true" || "${home_reachable}" != "true" ]]; then
  exit 1
fi
