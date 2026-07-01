# Phase 10 Market Intelligence v1

## Phase 10 目标

Phase 10 adds a separate Market Intelligence observation layer for broad fund and ETF market scanning.

It produces:

- full-market fund and ETF observation artifacts;
- rule-based theme classification;
- theme statistics and hot-theme candidates;
- market data quality notes;
- `dashboard/market.html`;
- optional daily ops integration.

It does not change the main scoring model, main risk logic, daily default provider, or main Markdown/HTML report conclusions.

## Boundary With Main Scoring And Risk

Market Intelligence is an observation layer only.

It can say:

- `值得观察`;
- `候选主题`;
- `样本不足`;
- `需要更多证据`;
- `数据质量 warning/degraded`.

It must not say:

- buy;
- sell;
- guaranteed return;
- production score approval.

All JSON outputs include `not_production_model=true`, `main_score_changed=false`, and `main_risk_changed=false` where applicable.

## market-scan Usage

Fixture scan:

```bash
python -m fund_agent.cli market-scan \
  --provider fixture \
  --output-dir outputs \
  --as-of 2026-06-23
```

AKShare scan:

```bash
python -m fund_agent.cli market-scan \
  --provider akshare \
  --cache-file data/cache/funds.sqlite \
  --themes-config configs/market_themes.yaml \
  --output-dir outputs
```

Options:

- `--provider fixture|akshare`
- `--cache-file data/cache/funds.sqlite`
- `--themes-config configs/market_themes.yaml`
- `--output-dir outputs`
- `--as-of YYYY-MM-DD`
- `--top-n 20`
- `--min-theme-sample-size 5`

If AKShare live data is unavailable, the command tries cache fallback. If provider and cache both have no rows, it exits with a clear error.

## market_themes.yaml Rules

Rules live in:

```bash
configs/market_themes.yaml
```

Each rule can use:

- `name`
- `keywords`
- `fund_types`
- `metadata_keywords`
- `exchange_traded`

A fund may match multiple themes. The first version uses deterministic rules only; no LLM or news interpretation is used.

Unmatched funds are classified as `unknown`.

`confidence` is rule-match confidence only. It is not investment confidence.

## market_intelligence_report.json

Path:

```bash
outputs/market/market_intelligence_report.json
```

Run bundle copy:

```bash
outputs/runs/YYYY-MM-DD/market_intelligence_report.json
```

Core fields:

- `schema_version`
- `generated_at`
- `as_of`
- `source`
- `run_type`
- `total_funds`
- `total_etfs`
- `themes`
- `top_themes`
- `hot_theme_candidates`
- `insufficient_sample_themes`
- `data_quality_summary`
- `warnings`
- `not_production_model`
- `main_score_changed`
- `main_risk_changed`
- `records`
- `classifications`

Historical return windows may be missing. Missing windows create data quality warnings but do not fail the scan.

## market_intelligence_summary.md

Path:

```bash
outputs/market/market_intelligence_summary.md
```

Run bundle copy:

```bash
outputs/runs/YYYY-MM-DD/market_intelligence_summary.md
```

The summary includes:

- run date;
- data source;
- full-market fund count;
- ETF count;
- theme count;
- data quality summary;
- hot-theme candidates;
- insufficient-sample themes;
- classification warnings;
- explicit observation-only disclaimers.

Downstream agents should read JSON, not Markdown.

## dashboard/market.html

`generate-evidence-dashboard` now writes:

```bash
outputs/dashboard/market.html
```

It reads JSON artifacts only. If Market Intelligence has not run, it shows:

```text
Market Intelligence 尚未运行
```

The page displays:

- market run status;
- total funds and ETFs;
- theme count;
- hot-theme candidates;
- insufficient-sample themes;
- data quality;
- warning list;
- latest report path;
- `not_production_model=true`.

## Daily Ops Integration

Market Intelligence is disabled by default.

Enable it explicitly:

```bash
PROVIDER=akshare OUTPUT_DIR=outputs ENABLE_MARKET_INTELLIGENCE=true scripts/run_daily_ops.sh
```

For launchd automation, reinstall the daily job with:

```bash
PROVIDER=akshare ENABLE_MARKET_INTELLIGENCE=true bash scripts/install_launchd_scheduler.sh --daily
```

When enabled, daily ops runs:

```bash
python -m fund_agent.cli market-scan \
  --provider ${PROVIDER:-fixture} \
  --output-dir ${OUTPUT_DIR:-outputs} \
  --as-of ${AS_OF:-today}
```

If market-scan fails, daily ops records a warning and continues. This preserves the existing daily ops success path.

## Why No News, Announcements, Or Sentiment

Phase 10 only uses structured fund/ETF data and deterministic classification rules.

News, announcements, and sentiment require:

- source quality controls;
- timestamp alignment;
- attribution and quote rules;
- event-to-theme mapping;
- stronger hallucination and stale-data controls.

Those belong in a later Market Intelligence phase.

## Why No Historical Backfill

Phase 10 does not fabricate past run dates and does not run historical backfill.

Backfill needs separately marked historical data, distinct from live daily ops evidence. Mixing current live data into old `AS_OF` folders would pollute long-horizon readiness evidence.

## Phase 11 / Phase 12 Suggestions

Phase 11:

- add historical market snapshots with explicit backfill markers;
- compare theme trends across real historical snapshots;
- add richer ETF/fund metadata quality gates.

Phase 12:

- add structured news/announcement ingestion with source attribution;
- add event-to-theme evidence mapping;
- keep it separate from main scoring until a review gate approves integration.
