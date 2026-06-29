# Phase 4 Scoring/Risk Experiment Sandbox

## Phase 4 目标

Phase 4 adds an isolated experiment sandbox that can calculate `experiment_score` and `experiment_risk_issues` from `signal_candidates.json`.

It does not:

- change the main scoring model;
- change the main risk logic;
- change the daily default provider;
- change Markdown/HTML main report conclusions;
- perform trading or promise returns.

## 为什么不直接修改主评分/主风险

Signal candidates are still experimental inputs. They need threshold review, historical stability checks, and regression baselines before they can affect production score or risk output.

The sandbox writes separate files only:

- `outputs/experiment_scoring_report.json`
- `outputs/experiment_scoring_explained.md`
- optional snapshot `experiment_score_summary`

## `experiment_scoring.yaml`

Default config path:

```bash
configs/experiment_scoring.yaml
```

Supported fields:

- `enable_return_signal`: enable candidate return signals.
- `enable_drawdown_signal`: enable drawdown signals.
- `enable_volatility_signal`: enable volatility signals.
- `enable_liquidity_signal`: enable liquidity signals.
- `enable_rating_signal`: enable rating signals.
- `max_score_adjustment`: cap absolute score delta per fund.
- `min_signal_confidence`: exclude signals below this metadata confidence.
- `exclude_warning_windows`: exclude warning-quality signals.
- `exclude_degraded_windows`: exclude degraded-quality signals.
- `exclude_stale_cache`: exclude signals whose metadata marks stale cache.

Missing config fields use conservative defaults.

## Usage

Run the sandbox:

```bash
python -m fund_agent.cli experiment-scoring \
  --report outputs/fund_agent_report.json \
  --signals outputs/signal_candidates.json \
  --config configs/experiment_scoring.yaml \
  --output outputs/experiment_scoring_report.json
```

Explain the sandbox output:

```bash
python -m fund_agent.cli explain-experiment-scoring \
  --input outputs/experiment_scoring_report.json \
  --output outputs/experiment_scoring_explained.md
```

## Output Shape

`experiment_scoring_report.json` includes:

- `not_production_model`
- `experiment_scores`
- `experiment_risk_issues`
- `applied_signal_summary`
- `excluded_signal_summary`
- `score_delta_summary`
- `warnings`
- `disclaimer`

`experiment_score` never overwrites main `score`, and `experiment_risk_issues` never overwrite main `risk_issues`.

## Experiment Risk Issues

First-pass sandbox risk issue types:

- `high_drawdown_candidate`
- `high_volatility_candidate`
- `degraded_data_blocked`
- `stale_cache_blocked`
- `low_confidence_signal`
- `missing_required_signal_data`

These are experiment-only warnings for manual review.

## Manual Review Checklist

- Confirm each applied signal's direction hypothesis.
- Confirm excluded signals were blocked for data quality, stale cache, or sample reasons.
- Compare score deltas against historical stability reports.
- Check whether any factor would have changed a main report conclusion.
- Add regression tests before any future main model integration.

## Future Main Model Entry Conditions

Before any signal affects main score or main risk:

- fixture/AKShare daily outputs must have a stable baseline;
- missing fields must never improve scores;
- stale cache must not silently improve scores;
- degraded/warning windows must remain excluded unless explicitly designed otherwise;
- snapshot deltas must explain score/risk changes;
- JSON contract validation must keep passing.
