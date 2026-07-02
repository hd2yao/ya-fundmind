# Project Structure

This document is the quick map for YA FundMind OS v1. It describes what each top-level directory and major runtime file does.

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
| `docs/` | Active V1 docs plus archived historical phase docs. | Yes |
| `outputs/` | Generated reports, dashboards, logs, snapshots, traces, and run bundles. | No |
| `.venv/` | Local Python environment. | No |

## Core Code Modules

| File | Responsibility |
| --- | --- |
| `fund_agent/cli.py` | Main command router for demo, daily, ops, market, backfill, fund detail, portfolio, news evidence, signal experiments, and Web Console. |
| `fund_agent/models.py` | Shared dataclasses such as fund records, provider health, signal candidates, and experiment results. |
| `fund_agent/providers.py` | Fixture, AKShare, and Tiantian provider boundaries plus normalization helpers. |
| `fund_agent/cache.py` | SQLite cache for funds, fund details, and NAV history. |
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
| `fund_agent/fund_detail.py` | Watchlist and single-fund detail drilldown. |
| `fund_agent/historical_backfill.py` | Historical backfill observation layer. |
| `fund_agent/news_evidence.py` | Fixture-backed news/announcement evidence collection. |
| `fund_agent/evidence_dashboard.py` | Static dashboard generation. |
| `fund_agent/web_console.py` | Streamlit-backed local Web Console. |
| `fund_agent/ops.py` | Ops status and latest summary generation. |
| `fund_agent/research_loop.py` | Daily/weekly research loop and run bundle writing. |
| `fund_agent/review_state.py` | Manual review state read/write helpers. |
| `fund_agent/signal_candidates.py` | Candidate signal generation and batch stability summaries. |
| `fund_agent/signal_experiment.py` | Tiantian signal eligibility experiment. |
| `fund_agent/experiment_scoring.py` | Independent scoring/risk experiment sandbox. |
| `fund_agent/signal_review.py` | Signal readiness review and promotion proposal outputs. |

## Active Documentation

| Path | Purpose |
| --- | --- |
| `README.md` | V1 user manual. |
| `docs/README.md` | Documentation index and retention policy. |
| `docs/architecture/v1-system-architecture.md` | V1 architecture and boundaries. |
| `docs/roadmap/v1-delivery-roadmap.md` | V1 milestone roadmap and completion status. |
| `docs/backlog/v1-todo.md` | V1 maintenance backlog rules. |
| `docs/backlog/v2-ideas.md` | Ideas intentionally deferred beyond V1. |
| `docs/contracts/*.md` | Machine-readable output contracts and versioning rules. |
| `docs/ops/*.md` | Scheduler and readiness semantics. |
| `docs/releases/v1.0.0-release-report.md` | V1 release verification report. |
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

## Cleanup Rules

- Delete local `.DS_Store`, `__pycache__`, `.pytest_cache`, and generated `outputs/` files when they are not needed locally.
- Do not commit runtime cache, logs, generated dashboards, or private environment files.
- Keep active V1 docs short and operational.
- Move old phase plans or research notes to `docs/archive/` instead of keeping them in active directories.
