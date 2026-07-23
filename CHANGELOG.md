# Changelog

## Unreleased

- Start the v2.2 Fund Data Terminal delivery track with a cache-first, on-demand historical NAV path for any fund present in the full-market index.
- Add AKShare `fund_open_fund_info_em` mapping, bad-row isolation, timeout/retry reuse, SQLite `fund_navs` persistence and explicit stale fallback.
- Add `GET /api/funds/{code}/history` with fixed windows, source, as-of, freshness, quality and non-production boundaries.
- Upgrade the fund detail drawer with an interactive 1m/3m/6m/1y/all NAV chart and responsive desktop/tablet/mobile layout.
- Keep bulk all-market historical backfill, multi-source reconciliation, main scoring, main risk, recommendations and trading out of this delivery slice.

## v2.1.0 - 2026-07-22

- Promote the isolated Product Web Console into a local-first release candidate without changing the V2 research contracts or daily workflow.
- Add server-side full-market fund search, filtering, pagination and evidence-oriented fund detail views backed by structured market artifacts.
- Add an independent loopback-only launchd service so code upgrades require an explicit deploy while daily JSON updates appear without rebuilding the frontend.
- Package the production React assets inside the Python wheel and preserve the Streamlit fallback command.
- Validate 21,570 live AKShare market records, three primary responsive viewports and the 940px navigation boundary.
- Keep main scoring, main risk, provider defaults, watchlist, portfolio, daily/weekly schedules, trading and broker boundaries unchanged.

## v2.0.0 - 2026-07-17

- Released the evidence-grounded, local, read-only YA FundMind OS V2 Research Copilot after all M1-M6 acceptance gates passed.
- Accepted three distinct post-RC scheduler runs from 2026-07-15, 2026-07-16 and 2026-07-17, all bound to `2.0.0rc1` and exact commit `aaf526fa6d67b6933a67b908021df9419a83c786` with clean provenance.
- Confirmed AKShare live row counts of 19,987, 21,546 and 21,536 with no fallback, critical warning or degraded quality; strict report/snapshot/trace contracts passed for every accepted run.
- Re-ran full offline tests, compileall, strict contracts, six-topic CLI end-to-end checks, optional MCP integration, responsive Web Console checks, scheduler status and fresh release-readiness before the Final merge gate.
- Preserved the V1 daily/weekly workflow, main scoring, main risk, provider defaults, watchlist, portfolio and scheduler schedule.
- Kept the separate product Web Console work in Draft PR #32; it is not part of `v2.0.0` and will use an independent later version gate.
- No broker integration, automatic trading, buy/sell recommendations or return promises were added.

## v2.0.0-rc.1 - 2026-07-15

- Completed V2 M6 compatibility, security, privacy, performance and end-to-end hardening without changing V1 scoring, risk or scheduled research behavior.
- Added strict `release-readiness` output and contract with separate `historical_compat` and provenance-bound `post_rc` observation modes.
- Added daily run provenance for application version, exact Git commit, clean/dirty state, trigger and Python version; Final cannot be released from pre-RC history.
- Added recursive secret/path redaction and trusted-root, no-follow append-only audit writes that reject internal symlink escapes while supporting valid macOS system path aliases.
- Hardened Chinese/English trading, position and return-guarantee guardrails, including whitespace bypasses, and forced unsafe optional renderers back to deterministic output.
- Added strict schema validation, V1 compatibility/non-mutation matrices, 100-artifact performance budgets and six-topic CLI/MCP/Web end-to-end gates.
- Added interruptible AKShare provider deadlines on supported POSIX main-thread calls while preserving retry, trace and cache fallback behavior.
- Added offline socket blocking for the default pytest suite and Python 3.10/3.12 GitHub Actions coverage.
- Added V1-to-V2 migration, troubleshooting, performance-budget and RC release evidence documentation.
- Verified `414 passed, 1 skipped`, compileall, official MCP `1.28.1` integration (`44 passed`), responsive Web Console, real scheduler status and 16 historical AKShare compatibility runs.
- RC publication is not Final approval: `v2.0.0` still requires three different dates of clean, scheduler-generated `2.0.0rc1` runs from the exact RC main commit.

## v1.5.0 - 2026-07-13

- Added a local Research Copilot page backed by the public `ResearchCopilot` service and structured Research Answer JSON.
- Added question examples, deterministic answer status, confidence, as-of metadata, findings, citations, data gaps, quality warnings and redacted research audit display.
- Structured Home, Market, Funds, Portfolio, News, Review and Reports pages while keeping bounded source JSON previews for auditability.
- Added responsive 375/768/1440 layouts, wrapped navigation, stable metric geometry, 44px controls, keyboard focus states and reduced-motion handling.
- Added answered, empty, partial, unavailable, refused, unsupported and runtime-error presentation without requiring an LLM or network.
- Fixed Web Console review-state resolution so the default follows `--output-dir` instead of reading a relative `outputs/` path from the process working directory.
- Kept Run Daily, dashboard refresh and manual review writes within their existing boundaries; Copilot writes only its answer and append-only audit artifacts.
- Verified `352 passed, 1 skipped`, compileall, demo, daily/market fixture, all V1/V2 contracts, Research Copilot CLI, MCP/Skill no-dependency coverage, Web dry-run and Playwright desktop/tablet/mobile acceptance.
- No scoring, risk, provider-default, watchlist, portfolio, scheduler, trading or broker behavior changes.

## v1.4.0 - 2026-07-13

- Added framework-independent read-only status, catalog, query, ask and evidence adapters with strict argument allowlists.
- Added path, URL, command, configuration-write, transaction and unsupported-tool rejection tests.
- Added bounded async tool timeout, safe error taxonomy and append-only redacted MCP audit records.
- Added optional stable MCP Python SDK dependency `mcp>=1.28.1,<2`, FastMCP stdio/Streamable HTTP server and `mcp-server` CLI.
- Added official in-memory MCP client integration coverage while keeping default CI free of MCP and network requirements.
- Added `mcp-tool-result-v1` contract and `validate-contract --mcp-result`.
- Added the repository-local `ya-fundmind-research` Skill after governance review; it is not globally installed.
- Fixed editable package discovery so modern setuptools installs only `fund_agent*`; default CI now verifies `pip install -e ".[dev]"`.
- Verified `336 passed, 1 skipped`, compileall, demo, daily fixture, all contracts and Web Console dry-run; optional MCP environment verified `44 passed` with `mcp 1.28.1`.
- No scoring, risk, provider-default, watchlist, portfolio, scheduler, trading or broker behavior changes.

## v1.3.0 - 2026-07-13

- Added deterministic intent classification for market, fund, portfolio, news, history and data-quality research questions.
- Added read-only transaction and recommendation guardrails that take priority over research intent and prompt-injection text.
- Added deterministic Research Planner and structured ResearchAnswer output backed only by M1 Research Context and M2 Evidence Bundle findings.
- Added a no-LLM Chinese Markdown renderer plus an optional renderer interface that receives only a JSON deep copy and cannot mutate the structured answer.
- Added append-only redacted research audit records with question hash, bounded preview, status and evidence counts.
- Added `research-ask` CLI and `research-answer-v1` contract validation.
- Verified six real local research topics, blocked/unsupported handling and 44 JSON Pointer/content-hash round trips.
- Verified `293 passed`, compileall, demo, daily fixture, all V1/V2 contracts and Web Console dry-run.
- No scoring, risk, provider-default, watchlist, portfolio, scheduler, trading or broker behavior changes.

## v1.2.0 - 2026-07-13

- Added immutable EvidenceRef records with artifact id, content hash, RFC 6901 JSON Pointer, source, as-of, quality, stale state, original value and bounded excerpt.
- Added ResearchFinding and EvidenceBundle models; findings cannot exist without evidence references.
- Added market, fund, portfolio, news, history and quality finding builders using explicit field allowlists.
- Added quality gates for fallback, provider/artifact warnings, legacy schema, insufficient samples, stale/degraded data and critical warnings.
- Added cross-source conflict detection and mandatory review for degraded/blocked/conflicting evidence.
- Added source integrity checks that reject artifacts changed after Research Context generation.
- Added `build-research-evidence` CLI and `evidence-bundle-v1` contract validation.
- Verified `269 passed`, compileall, demo, daily fixture, market-scan, six real local topic bundles, pointer round-trip and Web Console dry-run.
- No scoring, risk, provider-default, watchlist, portfolio, scheduler, trading or broker behavior changes.

## v1.1.0 - 2026-07-13

- Added a whitelist Artifact Catalog covering V1 reports, snapshots, traces, market, fund detail, portfolio, news, ops, daily and weekly JSON artifacts.
- Added stable artifact identifiers, SHA-256 content hashes, source/as-of/quality/stale metadata, and deterministic discovery order.
- Added a contract-aware loader that safely handles missing, invalid, legacy-schema and non-object JSON while blocking path traversal and unregistered paths.
- Added compact `market`, `fund`, `portfolio`, `news`, `history`, and `quality` Research Context queries without parsing Markdown/HTML or copying full market record arrays.
- Added `research-query` CLI and `research-context-v1` contract validation.
- Added V2 architecture, roadmap, acceptance spec, task mapping and execution contract as the delivery baseline.
- Verified `242 passed`, compileall, demo, daily fixture, market-scan, Research Context validation and Web Console dry-run.
- No scoring, risk, provider-default, watchlist, portfolio, scheduler, trading or broker behavior changes.

- Entered V2 Research Copilot delivery mode while keeping `v1.0.3` as the stable runtime baseline.
- Added the V2 design, architecture, M1-M6 roadmap, acceptance spec, task mapping, implementation plan, execution contract, and P0/P1/P2 backlog.
- Defined checkpoint versions from `v1.1.0` through `v1.5.0`, followed by `v2.0.0-rc.1` and final `v2.0.0`.
- V2 remains local, read-only, evidence-grounded, and usable without LLM; no scoring, risk, trading, broker, recommendation, or V1 contract behavior changes are included in this planning baseline.

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
