# Changelog

## v0.14.0 - 2026-07-02

V1 M2 Historical Backfill release checkpoint.

- Added `historical-backfill` CLI for observation-only historical backfill runs.
- Writes backfill artifacts under `outputs/backfill/`, `outputs/market/snapshots/`, and `outputs/runs/YYYY-MM-DD/` with `run_type=historical_backfill`.
- Keeps backfill output separate from live daily evidence and does not write daily research summaries.
- Added NAV history summary backfill output for Fund Detail consumption.
- Added market trend backfill counters: `run_type_counts` and `backfill_snapshot_count`.
- Fund Detail can read backfill NAV summaries and shows `nav_history_run_type` / `nav_history_backfill` markers.
- Fixture backfill is explicitly marked as synthetic and not real history.
- Updated V1 roadmap/backlog status: M2 complete, M3 Portfolio Analysis next.
- No scoring, risk, watchlist, portfolio config, provider default, news, Web Console, or trading behavior changes.

## v0.13.1 - 2026-07-02

M1 Fund Detail unknown theme patch.

- Treat upstream `primary_theme="unknown"` as an unknown theme state.
- Populate `unknown_reason=theme_classification_unknown` for unknown theme classifications.
- Added regression coverage for unknown theme strings.
- No scoring, risk, watchlist, portfolio, provider default, backfill, news, Web Console, or trading behavior changes.

## v0.13.0 - 2026-07-02

V1 M1 Fund Detail generalization release checkpoint.

- Generalized Fund Detail and Watchlist Detail for arbitrary watchlists without hardcoded fund codes.
- Added `unknown_reason`, `data_coverage`, and `peer_comparison` to fund detail outputs.
- Added watchlist-level `coverage_summary` for average coverage, unknown themes, and peer sample sufficiency.
- Updated dashboard fund pages to show coverage, theme, peer comparison, missing fields, and warnings.
- Updated ops-status and latest summary with fund detail coverage fields.
- Updated V1 roadmap/backlog status: M1 complete, M2 Historical Backfill next.
- No scoring, risk, watchlist, portfolio, provider default, backfill, news, Web Console, or trading behavior changes.

## v0.12.2 - 2026-07-02

V1 architecture freeze and roadmap baseline.

- Added V1 system architecture document with layer diagram and V1 boundaries.
- Added V1 delivery roadmap with six milestones from Fund Detail hardening through V1 release.
- Added V1 Todo backlog rules and V2 ideas backlog to keep non-blocking work out of the V1 delivery path.
- Updated README to mark the project as V1 delivery mode.
- No scoring, risk, watchlist, portfolio, provider default, news, backfill, Web Console, or trading behavior changes.

## v0.12.1 - 2026-07-02

Environment and scheduler patch release.

- Added a project-local `.venv` runtime for local execution, dependency isolation, and launchd stability.
- Installed AKShare and test dependencies into the project `.venv`.
- Reinstalled daily launchd with `PYTHON_BIN` pinned to the project `.venv` Python path.
- Verified `.venv` test and compile checks pass.
- No scoring, risk, watchlist, provider default, or trading behavior changes.

## v0.12.0 - 2026-07-01

Phase 12 release checkpoint.

- Added Fund Detail and Watchlist Drilldown observation layer for single funds and current watchlist funds.
- Added `fund-detail` and `watchlist-detail` CLI commands that read existing artifacts/cache and write JSON/Markdown drilldown outputs.
- Added dashboard `funds.html`, per-fund dashboard pages, ops-status fields, and latest-summary fund detail section.
- Added daily ops integration so Market Intelligence runs can produce watchlist drilldowns without changing the daily default provider.
- Current system remains research/observation only: no trading, no return promises, no main scoring/risk promotion.

## v0.11.0 - 2026-07-01

Phase 1 through Phase 11 release checkpoint.

- Added reliable local data cache, provider health, warnings, traces, JSON contracts, and contract validation.
- Added AKShare live path and Tiantian enrichment foundation, NAV summaries, diagnostics, and signal experiments.
- Added signal candidate, stability, explanation, scoring/risk experiment, calibration, review, and evidence collection layers.
- Added daily/weekly local ops automation, launchd scheduler support, latest summary, dashboard, and ops status.
- Added Market Intelligence v1, market snapshots, and market trend validation.
- Current system remains research/observation only: no trading, no return promises, no main scoring/risk promotion.

Versioning rule for the current pre-1.0 stage:

- Completed V1 Milestone feature checkpoints use minor versions, for example `v0.13.0`.
- Small fixes inside a milestone use patch versions, for example `v0.13.1`.
- V1 release completion maps to `v1.0.0`.
- Breaking output-contract changes should wait for an explicit major/minor decision before tagging.
