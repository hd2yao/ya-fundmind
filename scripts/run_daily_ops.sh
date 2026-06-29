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

cd "${PROJECT_DIR}"

"${PYTHON_BIN}" -m fund_agent.cli daily-research \
  --provider "${PROVIDER}" \
  --watchlist-file "${WATCHLIST_FILE}" \
  --portfolio-config "${PORTFOLIO_CONFIG}" \
  --output-dir "${OUTPUT_DIR}" \
  --as-of "${AS_OF}"

"${PYTHON_BIN}" -m fund_agent.cli weekly-research \
  --runs-dir "${OUTPUT_DIR}/runs" \
  --review-state "${REVIEW_STATE}" \
  --output "${OUTPUT_DIR}/weekly_research_summary.md" \
  --json-output "${OUTPUT_DIR}/weekly_research_summary.json" \
  --days 7

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

echo "latest_summary.md: ${OUTPUT_DIR}/latest_summary.md"
echo "dashboard: ${OUTPUT_DIR}/dashboard/index.html"
