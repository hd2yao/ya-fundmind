# Phase 6 Signal Threshold Review Gate

## Phase 6 目标

Phase 6 adds a review gate for signal threshold candidates. It creates structured readiness reviews, threshold candidate status, manual review queue items, and a promotion proposal.

It does not:

- change the main scoring model;
- change the main risk logic;
- change the daily default provider;
- change Markdown/HTML main report conclusions;
- perform trading or promise returns.

## 为什么仍不接主评分/主风险

The experiment sandbox has useful signals, but useful is not the same as production-ready. A signal must pass stability, data-quality, sensitivity, and manual review gates before a separate future main-model PR can even be considered.

`approved_for_main_candidate` means only that a reviewer may consider a future PR. It does not connect the signal to the main model.

## `signal_threshold_candidates.yaml`

Default path:

```bash
configs/signal_threshold_candidates.yaml
```

Each candidate may include:

- `signal_id_pattern`
- `category`
- `source`
- `direction_hypothesis`
- `min_required_points`
- `required_quality_grade`
- `exclude_if_stale`
- `exclude_if_warning`
- `exclude_if_degraded`
- `max_score_adjustment_candidate`
- `risk_gate_candidate`
- `review_status`

Valid `review_status` values:

- `proposed`
- `needs_data`
- `needs_review`
- `rejected`
- `approved_for_experiment`
- `approved_for_main_candidate`

## Readiness Review

Run:

```bash
python -m fund_agent.cli review-signal-readiness \
  --signals outputs/signal_candidates.json \
  --stability outputs/signal_stability_report.json \
  --baseline outputs/experiment_baseline_comparison.json \
  --sensitivity outputs/experiment_config_sensitivity.json \
  --thresholds configs/signal_threshold_candidates.yaml \
  --output outputs/signal_readiness_review.json
```

The output includes:

- `review_items`
- `recommended_for_experiment`
- `rejected_or_blocked`
- `needs_more_data`
- `manual_review_required`
- `summary`
- `warnings`

It also writes:

```bash
outputs/manual_review_queue.json
```

## Promotion Proposal

Run:

```bash
python -m fund_agent.cli generate-signal-promotion-proposal \
  --review outputs/signal_readiness_review.json \
  --output docs/reviews/signal_promotion_proposal.md
```

The proposal includes:

- current model-change status;
- signals that can continue experiment;
- signals needing more data;
- rejected or blocked signals;
- direction hypotheses;
- sample requirements;
- missing tests before any future main-model work;
- manual approval checklist.

## Manual Review Queue

`manual_review_queue.json` contains:

- `review_id`
- `signal_id`
- `recommended_status`
- `required_human_decision`
- `reason`
- `evidence`
- `created_at`

This queue is for human confirmation only. It never triggers automatic integration.

## Conditions Before A Separate Main-Model PR

A future main-model integration PR needs at least:

- stable signal history;
- sufficient eligible rate;
- no unresolved stale/missing/degraded/warning blockers;
- acceptable config sensitivity;
- explicit human approval;
- regression tests for main score and main risk behavior;
- snapshot comparison showing expected changes;
- contract validation remaining green.
