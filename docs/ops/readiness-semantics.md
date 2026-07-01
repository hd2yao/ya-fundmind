# Readiness Semantics

## Scope

Readiness fields describe different parts of the local research workflow. They must not be collapsed into a single project-level blocked status.

## ops_ready

`ops_ready=true` means the latest daily research loop can run and produce local artifacts.

Typical requirements:

- latest `daily-research` completed successfully;
- required JSON artifacts exist;
- `ops-status` can read the output directory.

`ops_ready=false` means the local run loop needs operational attention.

## dashboard_ready

`dashboard_ready=true` means `outputs/dashboard/index.html` exists and can be opened locally.

It does not mean signals are approved for production scoring. It only means the evidence dashboard is available.

## research_loop_ready

`research_loop_ready=true` means the daily evidence loop is usable for continued collection.

It allows:

- daily run bundle generation;
- weekly summary refresh;
- dashboard refresh;
- long-horizon stability measurement;
- continued feature development.

## main_model_ready

`main_model_ready=true` is much stricter. It means the system has enough evidence to consider a separate main-score or main-risk integration review.

It does not automatically change the main model.

When `main_model_ready=false`, the system may still be healthy for daily ops and feature development.

## Why 20 Runs

The current long-horizon rule requires at least 20 valid runs in a recent 30-day window before considering main model promotion.

This is a stability gate for main score and main risk only. It is not a blocker for:

- daily research;
- weekly research;
- dashboard use;
- Market Intelligence development;
- Fund Detail development;
- Research Console development.

## insufficient_history

`insufficient_history` means there are not enough valid run bundles to evaluate signal stability.

It should appear as a `main_model_blocker`, not as a system-level failure.

The correct interpretation is:

> Historical run shortage only affects main score/main risk promotion. It does not block daily research, dashboard use, continued development, or evidence collection.

## Valid Daily Run

A run is useful evidence when:

- daily status is `success`;
- contract validation passes;
- key JSON artifacts exist;
- data quality is not repeatedly `degraded`;
- provider fallback is absent or clearly explained;
- critical provider warnings are not recurring.

## Do Not Fake Past Runs

Do not create old run dates by setting `AS_OF` while using today's live data.

Example to avoid:

```bash
AS_OF=2026-06-10 PROVIDER=akshare scripts/run_daily_ops.sh
```

That produces a historical-looking folder using current live data. It pollutes stability evidence.

## Live Daily Run vs Historical Backfill

Live daily run:

- runs once on the current day;
- verifies provider, cache, contract, dashboard, and research loop behavior;
- is suitable for ops stability evidence.

Historical backfill:

- uses real historical data for past dates;
- must be explicitly marked as backfill;
- is useful for trend research;
- should not be mixed silently with live daily ops.

## When Backfill Is Needed

Backfill is useful when the goal is historical trend analysis, NAV-window statistics, or market/sector research.

It is not currently implemented in this phase.

## Current Stage

Continue daily ops and feature development in parallel.

Recommended next work:

- keep accumulating valid daily runs;
- review `outputs/latest_summary.md`;
- review `outputs/dashboard/index.html`;
- build Market Intelligence as a separate observation layer;
- keep main score and main risk unchanged until a future review gate.
