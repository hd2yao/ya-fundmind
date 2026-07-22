#!/usr/bin/env bash
set -euo pipefail

LABEL="com.ya-fundmind.web"
TARGET="${HOME}/Library/LaunchAgents/${LABEL}.plist"

if [[ -f "${TARGET}" ]]; then
  launchctl bootout "gui/$(id -u)" "${TARGET}" >/dev/null 2>&1 || true
  launchctl unload "${TARGET}" >/dev/null 2>&1 || true
  rm -f "${TARGET}"
  echo "uninstalled web: ${TARGET}"
else
  echo "web service is not installed: ${TARGET}"
fi
