# Scheduler Automation

## Architecture

Scheduler automation wraps the existing local commands:

- `scripts/run_daily_ops.sh`
- `scripts/run_weekly_ops.sh`
- `python -m fund_agent.cli ops-status`

It does not run Codex as a background service. The scheduler only invokes local shell scripts that write local files under `outputs/`.

## Manual Daily Run

```bash
PROVIDER=fixture OUTPUT_DIR=outputs scripts/run_daily_ops.sh
```

Use AKShare live data explicitly:

```bash
PROVIDER=akshare OUTPUT_DIR=outputs scripts/run_daily_ops.sh
```

Daily outputs include:

- `outputs/runs/YYYY-MM-DD/`
- `outputs/fund_agent_report.html`
- `outputs/latest_summary.md`
- `outputs/latest_summary.json`
- `outputs/ops_status.json`
- `outputs/dashboard/index.html`
- `outputs/logs/daily-ops-YYYY-MM-DD.log`

## Manual Weekly Run

```bash
OUTPUT_DIR=outputs DAYS=7 scripts/run_weekly_ops.sh
```

Weekly outputs include:

- `outputs/weekly_research_summary.md`
- `outputs/weekly_research_summary.json`
- `outputs/dashboard/index.html`
- `outputs/long_horizon_stability.json`
- `outputs/ops_status.json`
- `outputs/logs/weekly-ops-YYYY-MM-DD.log`

## macOS launchd Templates

Templates:

- `ops/launchd/com.ya-fundmind.daily.plist.template`
- `ops/launchd/com.ya-fundmind.weekly.plist.template`

Defaults:

- daily: every day at 18:30
- weekly: Saturday at 10:00
- provider: `fixture`

## Install launchd Jobs

Dry-run first:

```bash
bash scripts/install_launchd_scheduler.sh --daily --weekly --dry-run
```

Install:

```bash
bash scripts/install_launchd_scheduler.sh --daily --weekly
```

Install using AKShare:

```bash
PROVIDER=akshare bash scripts/install_launchd_scheduler.sh --daily --weekly
```

Override schedule:

```bash
DAILY_HOUR=18 DAILY_MINUTE=30 WEEKLY_WEEKDAY=6 WEEKLY_HOUR=10 WEEKLY_MINUTE=0 \
  bash scripts/install_launchd_scheduler.sh --daily --weekly
```

The install script writes plist files into `~/Library/LaunchAgents/`, validates them with `plutil` when available, and loads them with `launchctl bootstrap` or `launchctl load`.

## Status

```bash
bash scripts/status_launchd_scheduler.sh
```

The status script reports:

- daily installed status;
- weekly installed status;
- launchctl loaded status;
- plist paths;
- log paths;
- latest run;
- latest summary existence;
- ops status existence;
- dashboard existence.

It also refreshes `outputs/ops_status.json` and `outputs/latest_summary.md`.

## Uninstall

```bash
bash scripts/uninstall_launchd_scheduler.sh --daily --weekly
```

Uninstall only removes LaunchAgent plist files. It keeps logs and `outputs/`.

## Switch fixture to AKShare

The scheduler defaults to `PROVIDER=fixture` for conservative local automation.

Use AKShare by installing with:

```bash
PROVIDER=akshare bash scripts/install_launchd_scheduler.sh --daily --weekly
```

AKShare must be installed in the Python environment used by `PYTHON_BIN`.

## Logs

Runner logs:

- `outputs/logs/daily-ops-YYYY-MM-DD.log`
- `outputs/logs/weekly-ops-YYYY-MM-DD.log`

launchd stdout/stderr:

- `outputs/logs/launchd-daily.out.log`
- `outputs/logs/launchd-daily.err.log`
- `outputs/logs/launchd-weekly.out.log`
- `outputs/logs/launchd-weekly.err.log`

## Dashboard

Open:

```bash
open outputs/dashboard/index.html
```

Main report:

```bash
open outputs/fund_agent_report.html
```

## Linux cron Templates

Templates:

- `ops/cron/ya-fundmind.daily.crontab.template`
- `ops/cron/ya-fundmind.weekly.crontab.template`

They are not installed automatically.

Before use, replace `/absolute/path/to/ya-fundmind`.

## Why Codex Is Not A Resident Service

Codex is used to edit, review, and run local commands. It should not be treated as a daemon.

The durable automation boundary is:

- shell scripts;
- launchd or cron;
- local JSON/HTML/Markdown artifacts.

## Troubleshooting

Permissions:

```bash
chmod +x scripts/run_daily_ops.sh scripts/run_weekly_ops.sh
```

Python path:

```bash
PYTHON_BIN=/path/to/python bash scripts/install_launchd_scheduler.sh --daily --weekly
```

launchctl:

```bash
launchctl print gui/$(id -u)/com.ya-fundmind.daily
launchctl print gui/$(id -u)/com.ya-fundmind.weekly
```

AKShare:

- install AKShare in the selected Python environment;
- keep `PROVIDER=fixture` if live network access is unreliable.

Tiantian smoke:

- smoke commands are optional;
- daily scheduler does not require Tiantian smoke;
- set `FUND_AGENT_SKIP_TIANTIAN_SMOKE=true` for scheduler environments.
