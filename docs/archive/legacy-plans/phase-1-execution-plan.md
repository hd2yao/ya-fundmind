# Phase 1 Data Reliability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Land the first production-shaped data reliability layer for YA FundMind: local SQLite cache, normalized provider records, YAML watchlist/portfolio configs, and daily snapshots with report deltas.

**Architecture:** Keep the deterministic MVP intact. Add small stdlib-only modules around the current flow: cache sits under providers, config loading feeds the CLI, snapshots are written after `run_research()`, and report rendering reads optional delta metadata from `ResearchResult`.

**Tech Stack:** Python 3.10+ stdlib only (`sqlite3`, `json`, `datetime`, `pathlib`, `dataclasses`, `argparse`); pytest for tests. YAML support is implemented by a small local parser for the project config subset to avoid adding dependencies.

---

## P0/P1 Task Selection

Based on `docs/research/open-source-study.md`, `docs/research/current-mvp-gap-analysis.md`, and `docs/research/adoption-roadmap.md`, Phase 1 should land these five tasks first:

| Priority | Task | Why now | Acceptance |
| --- | --- | --- | --- |
| P0 | Data cache and stale fallback | Live data is the largest operational risk; reports must finish with warnings when providers fail. | SQLite cache stores fund basics, NAV, valuations, and details with `source`, `as_of`, `updated_at`, `expires_at`; live failure can use cache; stale usage appears in report. |
| P0 | Provider normalization contract | AKShare and future Eastmoney/Tiantian providers must not leak raw fields into scoring/reporting. | Fund code/name/category/nav dates/source fields are normalized; AKShare has explicit field mapping and exception handling; provider base interface leaves room for Eastmoney/Tiantian. |
| P1 | Watchlist and portfolio configs | Users need a local self-selected fund pool and holdings without editing fixture files. | `configs/watchlist.yaml` and `configs/portfolio.yaml` exist; CLI can read them; `demo` still uses fixture data by default. |
| P1 | Historical snapshots and deltas | Daily reports need movement: score, valuation, risk, and holding-risk changes from the previous run. | Each run writes `outputs/snapshots/YYYY-MM-DD.json`; report compares the previous snapshot and shows deltas when available. |
| P1 | Regression coverage and run verification | The MVP must stay runnable while adding data reliability. | New pytest coverage for cache, provider normalization, config loading, and snapshots; existing tests pass; `compileall` and demo report run succeed. |

## Implementation Boundaries

- Do not add Web, MCP, LLM, LangGraph, broker integration, trading execution, or return promises.
- Do not copy code from reference projects.
- Keep existing CLI commands and tests compatible.
- Use small commits, one independently reviewable change at a time.
- Keep generated runtime outputs under ignored `outputs/`.

## Task 1: SQLite Cache Layer

**Files:**
- Create: `fund_agent/cache.py`
- Test: `tests/test_cache.py`

**Step 1: Write failing tests**

Cover these behaviors:

- `FundCache.upsert_funds()` persists normalized `FundRecord` values into `fund_basics`.
- `FundCache.load_funds(as_of=...)` returns cached funds with `source` set to `cache:<original_source>`.
- Expired records are returned only when `allow_stale=True`, and their `metadata["stale"]` is true.
- Cache has tables for `fund_basics`, `fund_navs`, `fund_valuations`, and `fund_details`.

Run:

```bash
python -m pytest tests/test_cache.py -q
```

Expected: fail because `fund_agent.cache` does not exist.

**Step 2: Implement minimal cache**

Implement:

- `CacheRecordStatus`
- `FundCache`
- `init_schema()`
- `upsert_funds(funds, as_of, ttl_days=1)`
- `load_funds(as_of=None, allow_stale=False)`

Use JSON for `returns` and `metadata`, ISO strings for timestamps, and SQLite `INSERT ... ON CONFLICT`.

**Step 3: Verify**

Run:

```bash
python -m pytest tests/test_cache.py -q
python -m pytest -q
```

Expected: pass.

**Step 4: Commit**

```bash
git add fund_agent/cache.py tests/test_cache.py
git commit -m "feat: add sqlite fund cache"
```

## Task 2: Provider Normalization and Cache Fallback

**Files:**
- Modify: `fund_agent/models.py`
- Modify: `fund_agent/providers.py`
- Test: `tests/test_provider.py`

**Step 1: Write failing tests**

Cover these behaviors:

- `normalize_fund_code()` strips whitespace and preserves six-digit fund codes.
- `AkshareProvider` maps known AKShare fields through one mapping helper.
- Provider failures can fall back to cache when a `FundCache` is provided.
- Stale fallback records carry `metadata["stale"] == True`.
- Placeholder `EastmoneyProvider` and `TiantianFundProvider` exist and raise `ProviderUnavailable` with clear messages.

Run:

```bash
python -m pytest tests/test_provider.py -q
```

Expected: fail because normalization/fallback APIs do not exist.

**Step 2: Implement minimal provider contract**

Implement:

- `normalize_fund_code(value)`
- `normalize_fund_name(value)`
- `normalize_fund_category(value)`
- `ProviderResult` if needed for internal handling, but keep public `fetch_funds()` returning `list[FundRecord]`.
- AKShare mapping helper `_fund_from_akshare_row(row)`.
- Optional cache fallback in `AkshareProvider(cache=..., allow_stale_cache=True)`.
- `EastmoneyProvider` and `TiantianFundProvider` placeholders.

Keep existing `FixtureProvider` behavior unchanged.

**Step 3: Verify**

Run:

```bash
python -m pytest tests/test_provider.py tests/test_cache.py -q
python -m pytest -q
```

Expected: pass.

**Step 4: Commit**

```bash
git add fund_agent/models.py fund_agent/providers.py tests/test_provider.py
git commit -m "feat: normalize providers with cache fallback"
```

## Task 3: Watchlist and Portfolio Configs

**Files:**
- Create: `fund_agent/config.py`
- Create: `configs/watchlist.yaml`
- Create: `configs/portfolio.yaml`
- Modify: `fund_agent/cli.py`
- Test: `tests/test_config.py`
- Test: `tests/test_cli.py`

**Step 1: Write failing tests**

Cover these behaviors:

- `load_watchlist_config()` reads `configs/watchlist.yaml` and returns fund codes.
- `load_portfolio_config()` reads `configs/portfolio.yaml` and returns `PortfolioHolding` values.
- `screen --watchlist-file <path>` filters fetched funds to configured fund codes.
- `portfolio --portfolio-config <path>` reads YAML holdings.
- `demo` continues using fixture data and default example portfolio.

Run:

```bash
python -m pytest tests/test_config.py tests/test_cli.py -q
```

Expected: fail because config APIs and CLI flags do not exist.

**Step 2: Implement minimal config loader**

Implement a small YAML subset parser that supports:

- top-level scalar fields
- list of mappings under `funds:` and `holdings:`
- strings, floats, integers, and blank comments

Do not add PyYAML dependency.

**Step 3: Wire CLI**

Add flags:

- `--watchlist-file configs/watchlist.yaml`
- `--portfolio-config configs/portfolio.yaml`

Filtering applies only when a watchlist file is explicitly provided or when `screen` uses the default config and the file exists. `demo` should stay fixture-first.

**Step 4: Verify**

Run:

```bash
python -m pytest tests/test_config.py tests/test_cli.py -q
python -m pytest -q
```

Expected: pass.

**Step 5: Commit**

```bash
git add fund_agent/config.py fund_agent/cli.py configs/watchlist.yaml configs/portfolio.yaml tests/test_config.py tests/test_cli.py
git commit -m "feat: add watchlist and portfolio configs"
```

## Task 4: Historical Snapshots and Report Deltas

**Files:**
- Create: `fund_agent/snapshot.py`
- Modify: `fund_agent/agents.py`
- Modify: `fund_agent/report.py`
- Modify: `fund_agent/cli.py`
- Test: `tests/test_snapshot.py`
- Test: `tests/test_report.py`
- Test: `tests/test_cli.py`

**Step 1: Write failing tests**

Cover these behaviors:

- `write_snapshot(result, output_dir)` writes `snapshots/YYYY-MM-DD.json`.
- `load_previous_snapshot(output_dir, as_of)` finds the latest snapshot before `as_of`.
- `compare_snapshots(previous, current)` reports score, valuation, risk, and holding-risk deltas.
- CLI writes a snapshot on every successful report run.
- Markdown report includes a snapshot comparison section when deltas exist.

Run:

```bash
python -m pytest tests/test_snapshot.py tests/test_report.py tests/test_cli.py -q
```

Expected: fail because snapshot APIs and report deltas do not exist.

**Step 2: Implement snapshot model**

Use JSON with stable fields:

- `as_of`
- `candidates`: `code`, `name`, `score`, `evidence_label`
- `valuations`: `code`, `method`, `estimated_value`, `confidence`
- `portfolio`: total value, total return, risk issue messages, positions

Add optional `snapshot_delta` to `ResearchResult`.

**Step 3: Wire CLI and report**

After `run_research()`:

1. Load previous snapshot from `output_dir/snapshots`.
2. Compare previous/current.
3. Attach delta to result.
4. Write Markdown/HTML reports.
5. Persist current snapshot.

**Step 4: Verify**

Run:

```bash
python -m pytest tests/test_snapshot.py tests/test_report.py tests/test_cli.py -q
python -m pytest -q
```

Expected: pass.

**Step 5: Commit**

```bash
git add fund_agent/snapshot.py fund_agent/agents.py fund_agent/report.py fund_agent/cli.py tests/test_snapshot.py tests/test_report.py tests/test_cli.py
git commit -m "feat: add historical snapshots and report deltas"
```

## Task 5: Final Integration Verification and Documentation Touch-Up

**Files:**
- Modify: `README.md`
- Modify: `docs/plans/phase-1-execution-plan.md` if implementation notes need adjustment.

**Step 1: Update README**

Add concise notes for:

- SQLite cache path and stale fallback behavior.
- YAML watchlist/portfolio config files.
- Snapshot output path.

**Step 2: Run required verification**

Run:

```bash
python -m pytest -q
python -m compileall -q fund_agent
python -m fund_agent.cli demo --output-dir outputs --as-of 2026-06-22
```

Expected:

- pytest passes.
- compileall exits 0.
- demo writes `outputs/fund_agent_report.md`, `outputs/fund_agent_report.html`, and `outputs/snapshots/2026-06-22.json`.

**Step 3: Focused code review**

Review:

```bash
git diff --check
git diff --stat
git diff
git status --short
```

Look for:

- accidental generated outputs in tracked files.
- stale data not surfaced in report.
- config defaults breaking demo.
- new dependencies accidentally added.

**Step 4: Commit**

```bash
git add README.md docs/plans/phase-1-execution-plan.md
git commit -m "docs: document phase 1 data reliability workflow"
```

## Final Required Commands

Before final response:

```bash
python -m pytest -q
python -m compileall -q fund_agent
python -m fund_agent.cli demo --output-dir outputs --as-of 2026-06-22
git status --short
```

Then push the branch, create or update a PR, inspect checks, and merge only if gates pass.
