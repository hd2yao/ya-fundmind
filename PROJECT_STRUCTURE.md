# Project Structure

This document is the quick map for YA FundMind OS. V1 remains the stable runtime baseline; V2 Research Copilot completed the post-RC observation gate and was released as `v2.0.0`.

## Top-Level Directories

| Path | Purpose | Keep In Git |
| --- | --- | --- |
| `fund_agent/` | Application code: CLI, providers, cache, reporting, research loop, dashboard, Web Console, signal experiments. | Yes |
| `tests/` | Pytest coverage for CLI, providers, cache, contracts, reporting, ops, dashboard, Web Console, and experiment layers. | Yes |
| `configs/` | User-editable YAML configuration for watchlist, portfolio, providers, market themes, research loop, and experiments. | Yes |
| `data/fixtures/` | Stable fixture data used by demo/tests/offline runs. | Yes |
| `data/cache/` | Local SQLite cache created at runtime. | No |
| `scripts/` | Daily/weekly ops runners and launchd install/status/uninstall helpers. | Yes |
| `ops/` | Scheduler templates for launchd and cron. | Yes |
| `docs/` | Active V1/V2 architecture, roadmap, contracts, plans, ops and archived history. | Yes |
| `specs/` | V2 acceptance criteria, task mapping and execution contract. | Yes |
| `skills/` | Repository-local, manually invoked project Skills; not globally installed. | Yes |
| `outputs/` | Generated reports, dashboards, logs, snapshots, traces, and run bundles. | No |
| `.venv/` | Local Python environment. | No |

## Core Code Modules

| File | Responsibility |
| --- | --- |
| `fund_agent/cli.py` | Main command router for demo, daily, ops, market, backfill, fund detail, portfolio, news evidence, signal experiments, and Web Console. |
| `fund_agent/models.py` | Shared dataclasses such as fund records, provider health, signal candidates, and experiment results. |
| `fund_agent/providers.py` | Fixture, AKShare, and Tiantian provider boundaries plus normalization helpers. |
| `fund_agent/cache.py` | SQLite cache for funds, fund details, NAV history, market entities, and market time series. |
| `fund_agent/report.py` | Main Markdown/HTML/JSON report rendering. |
| `fund_agent/snapshot.py` | Snapshot writing and delta comparison. |
| `fund_agent/trace.py` | Provider trace writing and retention. |
| `fund_agent/contract.py` | JSON report / trace / snapshot contract validation. |
| `fund_agent/agents.py` | Main research orchestration using the stable scoring/risk pipeline. |
| `fund_agent/scoring.py` | Main scoring model. V1 does not auto-promote experimental signals into this file. |
| `fund_agent/valuation.py` | Valuation classification and valuation outputs. |
| `fund_agent/portfolio.py` | Portfolio config parsing and holding-level analysis helpers. |
| `fund_agent/portfolio_analysis.py` | Independent portfolio observation report. |
| `fund_agent/market_intelligence.py` | Market scan, market snapshots, and market trend outputs. |
| `fund_agent/market_history.py` | Allowlisted major-index history service with cache-first and stale fallback behavior. |
| `fund_agent/sector_history.py` | Industry-board catalog search and history service with fixed BK-code boundaries. |
| `fund_agent/fund_detail.py` | Watchlist and single-fund detail drilldown. |
| `fund_agent/historical_backfill.py` | Historical backfill observation layer. |
| `fund_agent/news_evidence.py` | Fixture-backed news/announcement evidence collection. |
| `fund_agent/evidence_dashboard.py` | Static dashboard generation. |
| `fund_agent/web_console.py` | Streamlit-backed local Console for Copilot, citations, quality, review, audit and V1 pages. |
| `fund_agent/ops.py` | Ops status and latest summary generation. |
| `fund_agent/research_loop.py` | Daily/weekly research loop and run bundle writing. |
| `fund_agent/review_state.py` | Manual review state read/write helpers. |
| `fund_agent/signal_candidates.py` | Candidate signal generation and batch stability summaries. |
| `fund_agent/signal_experiment.py` | Tiantian signal eligibility experiment. |
| `fund_agent/experiment_scoring.py` | Independent scoring/risk experiment sandbox. |
| `fund_agent/signal_review.py` | Signal readiness review and promotion proposal outputs. |
| `fund_agent/artifacts.py` | V2 whitelist Artifact Catalog and contract-aware safe JSON loader. |
| `fund_agent/research_query.py` | V2 compact market/fund/portfolio/news/history/quality query service. |
| `fund_agent/research_evidence.py` | V2 JSON Pointer citations, quality/conflict gate, and Evidence Bundle builder. |
| `fund_agent/research_copilot.py` | V2 intent guardrails, deterministic planner, and structured Research Answer. |
| `fund_agent/research_output.py` | Shared JSON/Markdown Research Answer writer used by CLI and Web without touching the main report. |
| `fund_agent/mcp_adapter.py` | Framework-independent allowlisted read-only Research MCP adapter. |
| `fund_agent/mcp_gateway.py` | MCP timeout, safe error mapping, and redacted append-only audit. |
| `fund_agent/mcp_server.py` | Optional FastMCP server and transport boundary. |
| `fund_agent/redaction.py` | Recursive secret and local-path redaction for public outputs and audits. |
| `fund_agent/safe_io.py` | No-follow append-only JSONL writes for audit artifacts. |
| `fund_agent/runtime_provenance.py` | Application/Git/trigger/Python provenance captured in daily run metadata. |
| `fund_agent/release_readiness.py` | Historical compatibility and strict post-RC release-readiness evaluation. |
| `fund_agent/web_api.py` | Loopback-only Product Web API for structured artifacts, fund history, index history, and industry-board browsing. |

## Active Documentation

| Path | Purpose |
| --- | --- |
| `README.md` | Current user manual and V2 delivery entry point. |
| `docs/README.md` | Documentation index and retention policy. |
| `docs/architecture/v1-system-architecture.md` | V1 architecture and boundaries. |
| `docs/architecture/v2-system-architecture.md` | V2 target architecture and read-only boundaries. |
| `docs/roadmap/v1-delivery-roadmap.md` | V1 milestone roadmap and completion status. |
| `docs/roadmap/v2-delivery-roadmap.md` | V2 M1-M6 goals, gates, versions and release rules. |
| `docs/backlog/v1-todo.md` | V1 maintenance backlog rules. |
| `docs/backlog/v2-todo.md` | V2 P0/P1/P2 execution backlog. |
| `docs/backlog/v2-ideas.md` | Ideas not selected for the active V2 mainline. |
| `docs/plans/2026-07-13-v2-research-copilot-*.md` | V2 design and implementation master plan. |
| `specs/v2-research-copilot/` | V2 spec, plan, tasks and execution contract. |
| `docs/contracts/*.md` | Machine-readable output contracts and versioning rules. |
| `docs/ops/*.md` | Scheduler and readiness semantics. |
| `docs/migrations/v1-to-v2.md` | Non-destructive V1-to-V2 upgrade and rollback guide. |
| `docs/releases/v1.0.0-release-report.md` | V1 release verification report. |
| `docs/releases/v2.0.0-rc.1-release-report.md` | V2 RC acceptance evidence and Final observation gate. |
| `docs/releases/v2.0.0-release-report.md` | V2 Final runtime, validation, and release evidence. |
| `docs/archive/` | Historical phase plans, research notes, and review artifacts retained for traceability. |

## Generated Outputs

`outputs/` is runtime data and should not be committed. Important generated files include:

- `outputs/latest_summary.md`
- `outputs/ops_status.json`
- `outputs/dashboard/index.html`
- `outputs/fund_agent_report.json`
- `outputs/runs/YYYY-MM-DD/`
- `outputs/snapshots/YYYY-MM-DD.json`
- `outputs/traces/provider-YYYY-MM-DD.json`
- `outputs/market/`
- `outputs/fund_details/`
- `outputs/portfolio/`
- `outputs/news/`
- `outputs/research_queries/`
- `outputs/evidence/`
- `outputs/copilot/`
- `outputs/audit/`
- `outputs/release/`

## Cleanup Rules

- Delete local `.DS_Store`, `__pycache__`, `.pytest_cache`, and generated `outputs/` files when they are not needed locally.
- Do not commit runtime cache, logs, generated dashboards, or private environment files.
- Keep active V1/V2 docs operational and avoid duplicating the same source of truth.
- Move old phase plans or research notes to `docs/archive/` instead of keeping them in active directories.
