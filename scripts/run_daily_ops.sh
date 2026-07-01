#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${YA_FUNDMIND_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-python}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs}"
AS_OF="${AS_OF:-$(date +%F)}"
PROVIDER="${PROVIDER:-fixture}"
WATCHLIST_FILE="${WATCHLIST_FILE:-configs/watchlist.yaml}"
PORTFOLIO_CONFIG="${PORTFOLIO_CONFIG:-configs/portfolio.yaml}"
REVIEW_STATE="${REVIEW_STATE:-${OUTPUT_DIR}/manual_review_state.json}"
DAYS="${DAYS:-30}"
WEEKLY_DAYS="${WEEKLY_DAYS:-7}"
REFRESH_DASHBOARD="${REFRESH_DASHBOARD:-true}"
ENABLE_MARKET_INTELLIGENCE="${ENABLE_MARKET_INTELLIGENCE:-false}"
MARKET_TREND_DAYS="${MARKET_TREND_DAYS:-30}"
MARKET_TREND_MIN_SNAPSHOTS="${MARKET_TREND_MIN_SNAPSHOTS:-3}"

cd "${PROJECT_DIR}"

mkdir -p "${OUTPUT_DIR}/logs"
# default log: outputs/logs/daily-ops-YYYY-MM-DD.log
LOG_FILE="${OUTPUT_DIR}/logs/daily-ops-${AS_OF}.log"
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "daily ops started: as_of=${AS_OF} provider=${PROVIDER} output_dir=${OUTPUT_DIR}"

"${PYTHON_BIN}" -m fund_agent.cli daily-research \
  --provider "${PROVIDER}" \
  --watchlist-file "${WATCHLIST_FILE}" \
  --portfolio-config "${PORTFOLIO_CONFIG}" \
  --output-dir "${OUTPUT_DIR}" \
  --as-of "${AS_OF}"

if [[ "${ENABLE_MARKET_INTELLIGENCE}" == "true" ]]; then
  if ! "${PYTHON_BIN}" -m fund_agent.cli market-scan \
    --provider "${PROVIDER}" \
    --output-dir "${OUTPUT_DIR}" \
    --as-of "${AS_OF}"; then
    echo "market intelligence warning: market-scan failed; daily ops will continue"
  fi
  if ! "${PYTHON_BIN}" -m fund_agent.cli market-trend \
    --market-dir "${OUTPUT_DIR}/market" \
    --output-dir "${OUTPUT_DIR}" \
    --days "${MARKET_TREND_DAYS}" \
    --min-snapshots "${MARKET_TREND_MIN_SNAPSHOTS}"; then
    echo "market trend warning: market-trend failed; daily ops will continue"
  fi
  if ! "${PYTHON_BIN}" -m fund_agent.cli watchlist-detail \
    --watchlist-file "${WATCHLIST_FILE}" \
    --portfolio-config "${PORTFOLIO_CONFIG}" \
    --output-dir "${OUTPUT_DIR}"; then
    echo "watchlist detail warning: watchlist-detail failed; daily ops will continue"
  fi
else
  echo "market intelligence skipped: ENABLE_MARKET_INTELLIGENCE=${ENABLE_MARKET_INTELLIGENCE}"
fi

"${PYTHON_BIN}" -m fund_agent.cli weekly-research \
  --runs-dir "${OUTPUT_DIR}/runs" \
  --review-state "${REVIEW_STATE}" \
  --output "${OUTPUT_DIR}/weekly_research_summary.md" \
  --json-output "${OUTPUT_DIR}/weekly_research_summary.json" \
  --days "${WEEKLY_DAYS}"

if [[ "${REFRESH_DASHBOARD}" == "true" ]]; then
  "${PYTHON_BIN}" -m fund_agent.cli generate-evidence-dashboard \
    --runs-dir "${OUTPUT_DIR}/runs" \
    --review-state "${REVIEW_STATE}" \
    --output-dir "${OUTPUT_DIR}/dashboard" \
    --days "${DAYS}"
else
  echo "dashboard refresh skipped: REFRESH_DASHBOARD=${REFRESH_DASHBOARD}"
fi

"${PYTHON_BIN}" -m fund_agent.cli evaluate-long-horizon-stability \
  --runs-dir "${OUTPUT_DIR}/runs" \
  --days "${DAYS}" \
  --output "${OUTPUT_DIR}/long_horizon_stability.json"

"${PYTHON_BIN}" -m fund_agent.cli ops-status \
  --output-dir "${OUTPUT_DIR}" \
  --json-output "${OUTPUT_DIR}/ops_status.json" \
  --write-latest-summary

echo "latest_summary.md: ${OUTPUT_DIR}/latest_summary.md"
echo "latest_summary.json: ${OUTPUT_DIR}/latest_summary.json"
echo "dashboard: ${OUTPUT_DIR}/dashboard/index.html"
echo "daily ops log: ${LOG_FILE}"
