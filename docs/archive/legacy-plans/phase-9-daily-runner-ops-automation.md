# Phase 9 Daily Runner & Ops Automation

## Phase 9 目标

Phase 9 packages the existing research loop into local automation entrypoints.

It helps run these steps without typing them manually every day:

- `daily-research`
- `weekly-research`
- `generate-evidence-dashboard`
- `evaluate-long-horizon-stability`
- `ops-status`
- `latest_summary.md` generation

It does not:

- modify the main scoring model;
- modify the main risk logic;
- change the daily default provider;
- introduce complex Web, MCP, LLM, or LangGraph;
- trade or promise returns.

## Daily Ops Script

Run manually:

```bash
scripts/run_daily_ops.sh
```

Useful environment variables:

```bash
YA_FUNDMIND_PROJECT_DIR=/absolute/path/to/ya-fundmind
PYTHON_BIN=python
OUTPUT_DIR=outputs
AS_OF=2026-06-23
PROVIDER=fixture
WATCHLIST_FILE=configs/watchlist.yaml
PORTFOLIO_CONFIG=configs/portfolio.yaml
REVIEW_STATE=outputs/manual_review_state.json
DAYS=30
```

Outputs include:

- `outputs/runs/YYYY-MM-DD/`
- `outputs/latest_summary.md`
- `outputs/ops_status.json`
- `outputs/dashboard/index.html`
- `outputs/long_horizon_stability.json`

## Weekly Ops Script

Run manually:

```bash
scripts/run_weekly_ops.sh
```

This refreshes weekly summary, dashboard, long-horizon stability, ops status, and latest summary from existing run bundles.

## ops-status

Check local run state:

```bash
python -m fund_agent.cli ops-status \
  --output-dir outputs \
  --json-output outputs/ops_status.json \
  --write-latest-summary
```

`ops-status` reads JSON artifacts only and reports:

- latest run metadata;
- daily summary status;
- weekly run count;
- dashboard artifact existence;
- long-horizon blockers;
- `not_production_model=true`;
- `main_score_changed=false`;
- `main_risk_changed=false`.

## Latest Summary

`outputs/latest_summary.md` is a small human-readable operational summary. It is meant for quick daily checks, not for model decisions.

It includes:

- latest run date;
- daily status;
- data quality grade;
- main-model recommendation, usually `no`;
- weekly processed run count;
- manual review count;
- long-horizon blocker summary.

## launchd Template

Template:

```bash
ops/launchd/com.ya-fundmind.daily.plist.template
```

Usage sketch:

```bash
cp ops/launchd/com.ya-fundmind.daily.plist.template ~/Library/LaunchAgents/com.ya-fundmind.daily.plist
# Replace ${YA_FUNDMIND_PROJECT_DIR} and ${PYTHON_BIN}.
launchctl load ~/Library/LaunchAgents/com.ya-fundmind.daily.plist
```

## cron Template

Template:

```bash
ops/cron/ya-fundmind.crontab.template
```

Usage sketch:

```bash
crontab ops/cron/ya-fundmind.crontab.template
```

Edit `YA_FUNDMIND_PROJECT_DIR` before installing.

## Operational Boundary

The automation is local and file-based:

- it does not install itself;
- it does not send notifications;
- it does not call live providers unless you explicitly set a live provider path;
- it does not change configs automatically;
- it does not modify scoring or risk.

## Phase 10 Suggestions

- Add optional notification hooks that read `ops_status.json`.
- Add retention policy for old `outputs/runs` bundles.
- Add a local health check that validates launchd/cron installation without mutating system state.
