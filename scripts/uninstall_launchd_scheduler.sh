#!/usr/bin/env bash
set -euo pipefail

INSTALL_DAILY=false
INSTALL_WEEKLY=false
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"

usage() {
  cat <<'USAGE'
Usage: scripts/uninstall_launchd_scheduler.sh [--daily] [--weekly]

保留日志和 outputs；只卸载 LaunchAgent plist。
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --daily) INSTALL_DAILY=true ;;
    --weekly) INSTALL_WEEKLY=true ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

if [[ "${INSTALL_DAILY}" != "true" && "${INSTALL_WEEKLY}" != "true" ]]; then
  echo "nothing to uninstall; pass --daily and/or --weekly" >&2
  exit 2
fi

uninstall_one() {
  local kind="$1"
  local label="com.ya-fundmind.${kind}"
  local target="${LAUNCH_AGENTS_DIR}/${label}.plist"

  if [[ -f "${target}" ]]; then
    launchctl bootout "gui/$(id -u)" "${target}" >/dev/null 2>&1 || true
    launchctl unload "${target}" >/dev/null 2>&1 || true
    rm -f "${target}"
    echo "uninstalled ${kind}: ${target}"
  else
    echo "not installed ${kind}: ${target}"
  fi
}

[[ "${INSTALL_DAILY}" == "true" ]] && uninstall_one daily
[[ "${INSTALL_WEEKLY}" == "true" ]] && uninstall_one weekly
