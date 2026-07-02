# Phase 7 Evidence Collection & Daily Research Loop

## Phase 7 目标

Phase 7 adds a daily research loop that chains the existing report, contract validation, signal candidate, experiment scoring, baseline comparison, sensitivity, readiness review, and promotion proposal steps.

The purpose is evidence collection:

- accumulate daily run bundles;
- preserve machine-readable JSON artifacts;
- summarize daily and weekly research status;
- support manual review before any future model work.

It does not:

- change the main scoring model;
- change the main risk logic;
- change the daily default provider;
- change Markdown/HTML main report conclusions;
- perform trading or promise returns.

## 为什么仍不接主评分/主风险

Phase 6 concluded that no signal is ready for the main model:

- `recommended_for_experiment = 0`
- `needs_more_data = 3`
- `rejected_or_blocked = 1`
- `是否建议进入主模型 = no`

Phase 7 therefore only collects repeatable evidence. Main-model integration still needs stable history, clean data-quality gates, manual approval, and separate regression tests.

## daily-research 使用方式

```bash
python -m fund_agent.cli daily-research \
  --provider fixture \
  --watchlist-file configs/watchlist.yaml \
  --portfolio-config configs/portfolio.yaml \
  --output-dir outputs \
  --as-of 2026-06-23
```

`daily-research` runs:

1. daily report generation;
2. contract validation;
3. signal candidate generation;
4. experiment scoring;
5. experiment scoring explanation;
6. baseline comparison;
7. config sensitivity;
8. signal readiness review;
9. signal promotion proposal;
10. daily summary generation;
11. run bundle collection.

The command records each step as `success` or `failed`. Non-critical experiment/readiness failures are captured in the summary so the run remains useful for diagnosis. Daily report and contract validation failures are critical by default.

## weekly-research 使用方式

```bash
python -m fund_agent.cli weekly-research \
  --runs-dir outputs/runs \
  --output outputs/weekly_research_summary.md \
  --json-output outputs/weekly_research_summary.json \
  --days 7
```

The weekly summary reads recent run bundles and aggregates:

- processed run count;
- missing run dates;
- data-quality trend;
- provider warning trend;
- signal eligible trend;
- exclusion reason trend;
- applied signal trend;
- readiness status trend;
- manual review queue summary;
- recurring blockers.

It does not backtest, simulate trades, or produce trading instructions.

## outputs/runs 目录结构

Each daily run writes an evidence bundle:

```text
outputs/runs/YYYY-MM-DD/
  fund_agent_report.md
  fund_agent_report.html
  fund_agent_report.json
  snapshot.json
  provider_trace.json
  signal_candidates.json
  experiment_scoring_report.json
  experiment_scoring_explained.md
  experiment_baseline_comparison.json
  experiment_config_sensitivity.json
  signal_readiness_review.json
  manual_review_queue.json
  signal_promotion_proposal.md
  daily_research_summary.md
  daily_research_summary.json
  run_metadata.json
```

Missing artifacts are recorded in `daily_research_summary.json` instead of crashing the bundle step.

## daily_research_summary 字段

`daily_research_summary.json` includes:

- `as_of`
- `started_at`
- `finished_at`
- `duration_ms`
- `status`
- `steps`
- `data_source`
- `data_quality_grade`
- `provider_warnings`
- `signal_candidates`
- `experiment_scoring`
- `baseline_comparison`
- `config_sensitivity`
- `readiness_review`
- `manual_review_queue`
- `recommend_main_model`
- `main_score_changed`
- `main_risk_changed`
- `missing_artifacts`
- `not_production_model`

`recommend_main_model` is read from the promotion proposal and defaults to `no`.

## weekly_research_summary 字段

`weekly_research_summary.json` includes:

- `runs_processed`
- `missing_runs`
- `data_quality_trend`
- `provider_health_trend`
- `signal_eligible_trend`
- `top_exclusion_reasons_trend`
- `applied_signals_trend`
- `readiness_status_trend`
- `manual_review_queue_summary`
- `recurring_blockers`
- `recommendations_for_next_week`
- `not_production_model`
- `no_trading_simulation`

## Manual Review Queue 聚合

Weekly aggregation reads each run's `manual_review_queue.json` and reports:

- `total_review_items`
- `by_status`
- `by_signal_id`
- `repeated_review_items`
- `unresolved_items`

This aggregation never approves a signal automatically and never edits `configs/signal_threshold_candidates.yaml`.

## 后续何时可以考虑主模型接入

Only after repeated daily/weekly evidence shows stable signal quality, low exclusion noise, acceptable config sensitivity, and manual approval should a separate main-model PR be considered.

That future PR must include:

- main score regression tests;
- main risk regression tests;
- stale/missing/degraded data tests;
- snapshot delta tests;
- report conclusion safety checks.

## Phase 8 建议

- Add richer historical run dashboards from JSON artifacts only.
- Add manual review status import/export without automatic approval.
- Add long-horizon stability thresholds for `approved_for_experiment`.
- Keep main score and main risk unchanged until a separate reviewed integration phase.
