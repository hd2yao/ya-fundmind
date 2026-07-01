#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${YA_FUNDMIND_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-python}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs}"
REVIEW_STATE="${REVIEW_STATE:-${OUTPUT_DIR}/manual_review_state.json}"
DAYS="${DAYS:-30}"
AS_OF="${AS_OF:-$(date +%F)}"
MARKET_TREND_DAYS="${MARKET_TREND_DAYS:-30}"
MARKET_TREND_MIN_SNAPSHOTS="${MARKET_TREND_MIN_SNAPSHOTS:-3}"

cd "${PROJECT_DIR}"

mkdir -p "${OUTPUT_DIR}/logs"
# default log: outputs/logs/weekly-ops-YYYY-MM-DD.log
LOG_FILE="${OUTPUT_DIR}/logs/weekly-ops-${AS_OF}.log"
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "weekly ops started: as_of=${AS_OF} output_dir=${OUTPUT_DIR} days=${DAYS}"

"${PYTHON_BIN}" -m fund_agent.cli weekly-research \
  --runs-dir "${OUTPUT_DIR}/runs" \
  --review-state "${REVIEW_STATE}" \
  --output "${OUTPUT_DIR}/weekly_research_summary.md" \
  --json-output "${OUTPUT_DIR}/weekly_research_summary.json" \
  --days "${DAYS}"

if ! "${PYTHON_BIN}" -m fund_agent.cli market-trend \
  --market-dir "${OUTPUT_DIR}/market" \
  --output-dir "${OUTPUT_DIR}" \
  --days "${MARKET_TREND_DAYS}" \
  --min-snapshots "${MARKET_TREND_MIN_SNAPSHOTS}"; then
  echo "market trend warning: market-trend failed; weekly ops will continue"
fi

"${PYTHON_BIN}" -m fund_agent.cli generate-evidence-dashboard \
  --runs-dir "${OUTPUT_DIR}/runs" \
  --review-state "${REVIEW_STATE}" \
  --output-dir "${OUTPUT_DIR}/dashboard" \
  --days "${DAYS}"

"${PYTHON_BIN}" -m fund_agent.cli evaluate-long-horizon-stability \
  --runs-dir "${OUTPUT_DIR}/runs" \
  --days "${DAYS}" \
  --output "${OUTPUT_DIR}/long_horizon_stability.json"

"${PYTHON_BIN}" -m fund_agent.cli ops-status \
  --output-dir "${OUTPUT_DIR}" \
  --json-output "${OUTPUT_DIR}/ops_status.json" \
  --write-latest-summary

echo "weekly ops log: ${LOG_FILE}"
