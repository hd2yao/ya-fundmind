# Changelog

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

- Completed Phase N maps to `v0.N.0`.
- Small fixes inside a phase use patch versions, for example `v0.11.1`.
- Breaking output-contract changes should wait for an explicit major/minor decision before tagging.
