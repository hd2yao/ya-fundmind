# Scoring and Risk Input Contract

## Purpose

This document defines how Tiantian enrichment data may be considered for future scoring and risk work. Phase 2E does not connect Tiantian data to the scoring model or the risk main logic.

Downstream code should read structured JSON fields only:

- `fund_agent_report.json`
- provider trace JSON
- snapshot JSON

Do not parse Markdown or CLI stdout.

## Tiantian Fields That May Enter Future Scoring

Future scoring work may consider these fields only after enough validation and regression coverage exists:

- `fund_details.scale`: possible liquidity or capacity signal.
- `fund_details.rating`: possible external-quality signal.
- `nav_history_summary.windows.*.total_return`: possible window return signal.
- `nav_history_summary.windows.*.max_drawdown`: possible drawdown quality signal.
- `nav_history_summary.windows.*.volatility`: possible volatility quality signal.
- `nav_history_summary.windows.*.data_quality_grade`: gating signal for whether a window is usable.

These fields must not replace the existing scoring inputs without an explicit model change and regression review.

## Fields That Should Remain Display-Only

These fields should be shown for analyst context, not used as direct score inputs:

- `fund_details.fund_manager`
- `fund_details.fund_company`
- `fund_details.inception_date`
- `fund_details.metadata`
- Provider warning text
- Provider endpoint timing
- CLI output

Fund manager and company fields can be useful for manual research, but using them as numeric score inputs would require a separately designed credibility and tenure model.

## Minimum Sample Requirements

Before NAV windows can enter scoring or risk:

- `1m`: at least 15 valid NAV points.
- `3m`: at least 45 valid NAV points.
- `6m`: at least 90 valid NAV points.
- `1y`: at least 180 valid NAV points.
- `all`: may be used only for descriptive context unless a minimum window is also satisfied.

Any window with `data_quality_grade = "degraded"` must be excluded from scoring and main risk logic.

Any window with `data_quality_grade = "warning"` may be displayed and may be considered only if the consuming model explicitly handles partial samples.

## Short Window and Annualized Return Rules

Annualized return from short samples can be misleading. If a summary has:

- `metadata.annualized_return_unstable = true`
- fewer than 20 NAV points
- fewer than 30 calendar days

then `annualized_return` must not be used as a direct score input. It may only be displayed with a short-sample warning.

## Rating, Scale, and Manager Credibility Rules

Before future scoring uses detail fields:

- `rating` must include source, as-of date, and missing/unknown handling.
- `scale` must be normalized to a consistent unit and checked for stale cache.
- `fund_manager` must not be treated as a numeric quality factor unless there is a separate manager-tenure and track-record data source.
- `fund_company` must not be used as a score input without a documented whitelist, mapping, and bias review.

## Missing Field Handling

Missing Tiantian fields must not be silently converted into neutral-positive signals.

Recommended handling:

- Missing optional display fields: show `null` or `--`.
- Missing scoring candidate fields: exclude the specific factor.
- Missing critical NAV windows: mark the window `degraded`.
- Stale cache: require manual review before using the field in automated downstream logic.

## Why Phase 2E Does Not Connect Scoring or Risk

Phase 2E is a data-enrichment stabilization phase. It adds:

- NAV windows
- explicit Tiantian cache fallback
- trace metadata for fallback and windows
- machine-readable optional output fields

Connecting these data points to scoring or risk would change report behavior and require a separate model design, baseline comparison, and regression suite.

## Required Regression Tests Before Future Scoring/Risk Integration

Before Tiantian enrichment can affect scoring or main risk:

- Existing AKShare/fixture daily reports must remain stable.
- Score changes must be explainable for each new input factor.
- Missing Tiantian data must not improve a score.
- Stale Tiantian cache must not silently improve a score.
- Short-sample annualized return must not enter scoring.
- Window-level degraded data must be excluded.
- Historical snapshot comparison must show expected score/risk deltas.
- Contract validation must continue passing for JSON report, provider trace, and snapshot.
