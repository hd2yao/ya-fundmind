# Phase 8 Manual Review State + Evidence Dashboard

## Phase 8 目标

Phase 8 adds manual review state, static evidence dashboard generation, and long-horizon signal stability checks on top of Phase 7 run bundles.

It remains an observation and review layer only:

- no main scoring model changes;
- no main risk logic changes;
- no daily default provider changes;
- no Markdown/HTML main report conclusion changes;
- no MCP, LLM, LangGraph, trading, or return promises.

## 为什么仍不接主评分/主风险

Phase 6 and Phase 7 both show that current signals still need more evidence. Phase 8 records human review decisions and displays accumulated evidence, but it does not approve or connect any signal automatically.

`approved_for_main_candidate` in manual review state means only that a reviewer may consider a separate future PR. It does not modify the main model.

## `manual_review_state.json` 结构

Default path:

```bash
outputs/manual_review_state.json
```

Shape:

```json
{
  "items": [
    {
      "review_id": "demo-review",
      "signal_id": "tiantian:return",
      "status": "needs_more_data",
      "reviewer": "human",
      "decision": "needs_more_data",
      "note": "需要至少 30 天 run history",
      "updated_at": "2026-06-23T00:00:00+00:00",
      "evidence_refs": ["outputs/runs/2026-06-23"]
    }
  ]
}
```

Supported status values:

- `open`
- `approved_for_more_experiment`
- `rejected`
- `needs_more_data`
- `approved_for_main_candidate`

## update-review-state

```bash
python -m fund_agent.cli update-review-state \
  --review-id demo-review \
  --status needs_more_data \
  --note "需要更多历史 run" \
  --state outputs/manual_review_state.json
```

Optional fields:

- `--signal-id`
- `--reviewer`
- `--evidence-ref` repeated

This command only writes human review state. It never edits `configs/signal_threshold_candidates.yaml` and never changes scoring or risk.

## list-review-state

```bash
python -m fund_agent.cli list-review-state \
  --state outputs/manual_review_state.json
```

It prints a compact status summary and each tracked review item.

## weekly-research + review state

`weekly-research` now reads manual review state:

```bash
python -m fund_agent.cli weekly-research \
  --runs-dir outputs/runs \
  --review-state outputs/manual_review_state.json \
  --output outputs/weekly_research_summary.md \
  --json-output outputs/weekly_research_summary.json \
  --days 7
```

The weekly JSON includes `manual_review_state_summary`:

- `approved_count`
- `rejected_count`
- `needs_more_data_count`
- `unresolved_count`
- `signals_with_human_notes`

Manual state only affects summary display.

## Evidence Dashboard

Generate static HTML:

```bash
python -m fund_agent.cli generate-evidence-dashboard \
  --runs-dir outputs/runs \
  --review-state outputs/manual_review_state.json \
  --output-dir outputs/dashboard \
  --days 30
```

Generated files:

- `outputs/dashboard/index.html`
- `outputs/dashboard/runs.html`
- `outputs/dashboard/signals.html`
- `outputs/dashboard/review.html`
- `outputs/dashboard/data_quality.html`
- `outputs/dashboard/manifest.json`

Dashboard pages read JSON artifacts only. They do not parse Markdown and do not produce trading instructions. Each page marks `not_production_model=true`.

## Long-Horizon Stability

Run:

```bash
python -m fund_agent.cli evaluate-long-horizon-stability \
  --runs-dir outputs/runs \
  --days 30 \
  --output outputs/long_horizon_stability.json
```

Current conservative rules:

- fewer than 20 valid runs: `enough_history=false`;
- display-only signals are always `rejected`;
- recurring stale/missing/degraded/warning blockers prevent promotion;
- config sensitivity instability becomes `needs_review`;
- eligible rate below 0.6 becomes `needs_more_data`.

Output fields include:

- `runs_processed`
- `minimum_required_runs`
- `enough_history`
- `signal_stability_by_id`
- `eligible_rate_by_signal`
- `exclusion_reason_consistency`
- `data_quality_consistency`
- `config_sensitivity_consistency`
- `suggested_review_status`
- `blockers`

## 何时才考虑单独主模型接入 PR

A separate main-model PR can be considered only after:

- enough long-horizon run history exists;
- blockers are resolved or explicitly accepted;
- manual review state approves the direction;
- new main score and main risk regression tests are written;
- report and snapshot contracts remain valid;
- Markdown/HTML main conclusions remain safe.

Phase 8 does not perform that integration.
