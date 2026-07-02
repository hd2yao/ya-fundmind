# Phase 5 Experiment Calibration & Baseline Review

## Phase 5 目标

Phase 5 calibrates the Phase 4 experiment sandbox. It explains why signals are applied or excluded, adds controlled fixtures, compares main scores against experiment scores, and checks whether the sandbox is overly sensitive to config changes.

It does not:

- change the main scoring model;
- change the main risk logic;
- change the daily default provider;
- change Markdown/HTML main report conclusions;
- perform trading or promise returns.

## Why `applied signals = 0` Is Not Failure

`applied signals = 0` can be the correct outcome when all available signals are blocked by data quality, configuration gates, stale cache, unstable annualized return, or missing values.

The sandbox should explain that outcome instead of forcing signals into the experiment model. A zero-applied run is useful when it tells reviewers:

- which gate blocked the most signals;
- whether the block came from config, data quality, missing data, stale cache, or unstable annualized return;
- what must be fixed before any future main-model integration.

## Exclusion Diagnostics

`experiment_scoring_report.json` now includes `exclusion_diagnostics`:

- `excluded_by_reason`
- `excluded_by_category`
- `excluded_by_source`
- `excluded_by_quality_grade`
- `excluded_by_config`
- `excluded_by_missing_data`
- `excluded_by_stale_cache`
- `excluded_by_unstable_annualized_return`
- `primary_reason`

When no signals are applied, the report also emits a `zero_applied_signals` warning.

## Controlled Fixtures

Phase 5 adds controlled test fixtures:

- `tests/fixtures/fund_agent_report_experiment_mix.json`
- `tests/fixtures/signal_candidates_experiment_mix.json`

They cover:

- eligible return;
- eligible drawdown;
- eligible volatility;
- warning window exclusion;
- degraded window exclusion;
- unstable annualized return exclusion;
- display-only exclusion;
- stale cache exclusion;
- missing value exclusion.

These fixtures are test-only and do not affect demo, daily, or live provider paths.

## Baseline Comparison

Run:

```bash
python -m fund_agent.cli compare-experiment-baseline \
  --report outputs/fund_agent_report.json \
  --experiment outputs/experiment_scoring_report.json \
  --output outputs/experiment_baseline_comparison.json
```

Output includes:

- `total_funds`
- `adjusted_count`
- `unchanged_count`
- `avg_score_delta`
- `max_score_delta`
- `funds_with_adjustments`
- `funds_with_experiment_risk_issues`
- `main_score_vs_experiment_score`
- `warnings`
- `manual_review_required`

This is a comparison artifact only. It does not modify `fund_agent_report.json`.

## Manual Review Report

Run:

```bash
python -m fund_agent.cli explain-experiment-baseline \
  --input outputs/experiment_baseline_comparison.json \
  --output outputs/experiment_baseline_review.md
```

The Markdown report covers:

- whether the experiment changed scores;
- largest score deltas;
- exclusion reason distribution;
- whether the experiment should enter the main model;
- why it should not enter the main model yet;
- manual review items.

## Config Sensitivity

Run:

```bash
python -m fund_agent.cli experiment-config-sensitivity \
  --report outputs/fund_agent_report.json \
  --signals outputs/signal_candidates.json \
  --config configs/experiment_scoring.yaml \
  --output outputs/experiment_config_sensitivity.json
```

The first version checks:

- `max_score_adjustment` variants;
- return signal on/off;
- drawdown signal on/off;
- volatility signal on/off;
- warning-window exclusion on/off.

It does not backtest, attribute returns, or simulate trades.

## Manual Review Checklist

- Confirm that applied signals have enough sample quality.
- Confirm that excluded signals are blocked for defensible reasons.
- Review `primary_reason` when `applied signals = 0`.
- Compare score deltas against historical stability reports.
- Review config sensitivity for overreaction.
- Keep Markdown/HTML main report conclusions unchanged.

## Entry Conditions Before Main Score/Risk Integration

Before any experiment signal enters the main model:

- fixture and daily reports must have stable baselines;
- missing fields must never improve scores;
- stale cache must not improve scores;
- warning/degraded windows must remain gated unless explicitly designed;
- score/risk deltas must be explainable in snapshots;
- contract validation must keep passing;
- manual review must approve direction assumptions and thresholds.

## Why This Phase Still Does Not Change The Main Model

Phase 5 is calibration and evidence gathering. The system is still learning which signals are reliable enough to consider. Changing the main model here would turn an experiment into a user-facing conclusion before the evidence is ready.
