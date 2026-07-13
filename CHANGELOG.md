# Changelog

## v1.0.3 - 2026-07-13

Weekly scheduler runtime fix.

- Fixed the weekly launchd job failure caused by a relative `PYTHON_BIN=python` value under launchd's restricted `PATH`.
- The launchd installer now defaults to the project `.venv/bin/python` when available and writes an absolute interpreter path into daily/weekly plist files.
- Explicit command names supplied through `PYTHON_BIN` are resolved to absolute executable paths before installation.
- Plist rendering now uses the same resolved Python interpreter as the installed job.
- Added regression coverage for the project virtual-environment default.
- No scoring, risk, provider default, watchlist, portfolio, output-contract, or trading behavior changes.

## v1.0.2 - 2026-07-03

V1 post-release acceptance notes.

- Recorded the V1 post-release acceptance and ops check findings in `docs/backlog/v1-todo.md`.
- Confirmed daily scheduler, generated outputs, Web Console, contract validation, pytest, and compileall status.
- Classified current observations as non-blocking P2 items: history accumulation, portfolio valuation coverage, fund detail coverage, news evidence confidence, market sample coverage, and scheduler status wording.
- No runtime behavior, scoring, risk, provider default, watchlist, portfolio, scheduler install, or trading behavior changes.

## v1.0.1 - 2026-07-02

V1 documentation and repository structure cleanup.

- Added `PROJECT_STRUCTURE.md` as the quick map for directories, code modules, active docs, and generated outputs.
- Added `docs/README.md` as the documentation index and retention policy.
- Moved historical Phase plans, initial research notes, and old review artifacts into `docs/archive/`.
- Kept active V1 docs focused on architecture, roadmap, backlog, contracts, ops, and release reports.
- No runtime behavior, scoring, risk, provider default, watchlist, portfolio, scheduler, or trading behavior changes.

## v1.0.0 - 2026-07-02

YA FundMind OS V1 release.

- Finalized the V1 local personal fund/ETF research workstation scope.
- Rewrote README as the V1 usage manual covering install, configuration, daily/weekly ops, scheduler, Web Console, outputs, dashboard, backfill, fund detail, portfolio, news evidence, and risk boundaries.
- Added V1 release report at `docs/releases/v1.0.0-release-report.md`.
- Updated roadmap/backlog status: M1 through M6 complete.
- V1 remains research-only: no broker integration, no automatic trading, no return promises, no buy/sell advice, and no unauthorized main scoring/risk model changes.

## v0.17.0 - 2026-07-02

V1 M5 Web Console v1 release checkpoint.

- Added `web-console` CLI with Streamlit-backed local console startup.
- Added dry-run mode so default tests and local validation do not require a long-running web server.
- Added `fund_agent/web_console.py` with ops status, latest summary, Market, Funds, Portfolio, News, Review, and Reports views.
- Added Web Console helpers to refresh dashboard, trigger daily ops, and update manual review state.
- Added optional `web` dependency group for Streamlit.
- Updated V1 roadmap/backlog status: M5 complete, M6 V1 Release next.
- No scoring, risk, watchlist, portfolio config, provider default, trading, or main-report conclusion changes.

## v0.16.0 - 2026-07-02

V1 M4 News / Announcement Evidence release checkpoint.

- Added `collect-news-evidence` CLI for local fixture-backed news/announcement evidence collection.
- Writes `outputs/news/news_evidence_report.json`, `outputs/news/news_evidence_summary.md`, and `outputs/runs/YYYY-MM-DD/news_evidence_report.json`.
- Normalizes source, timestamps, related themes, related funds, evidence strength, source quality, and low-confidence warnings.
- Deduplicates repeated evidence rows and keeps skipped/mapping warnings in the output.
- Adds dashboard `news.html` and index links for News Evidence.
- Adds daily ops integration; news evidence failures are warnings and do not stop the daily run.
- Updated V1 roadmap/backlog status: M4 complete, M5 Web Console v1 next.
- No scoring, risk, watchlist, portfolio config, provider default, Web Console, trading, or main-report conclusion changes.

## v0.15.0 - 2026-07-02

V1 M3 Portfolio Analysis release checkpoint.

- Added independent `portfolio-analysis` CLI for observation-only portfolio reporting.
- Writes `outputs/portfolio/portfolio_report.json` and `outputs/portfolio/portfolio_report.md`.
- Copies portfolio analysis outputs into `outputs/runs/YYYY-MM-DD/` when `as_of` is available.
- Adds theme exposure, fund type exposure, concentration summary, and observation issues such as theme overlap and single-holding concentration.
- Adds dashboard `portfolio.html` and index links.
- Adds ops-status/latest-summary portfolio availability, status, holding count, total value, cash, and observation issue fields.
- Empty portfolio configs now produce a clear non-failing `portfolio_not_configured` report.
- Updated V1 roadmap/backlog status: M3 complete, M4 News / Announcement Evidence next.
- No scoring, risk, watchlist, portfolio config, provider default, news ingestion, Web Console, or trading behavior changes.

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
