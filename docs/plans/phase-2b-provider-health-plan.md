# Phase 2B Provider Health Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Establish the provider-health foundation before full Phase 2B: clean local artifacts, add CI, prepare AKShare live smoke validation, and define the next small fixes for provider robustness.

**Architecture:** Keep the current deterministic CLI and provider boundary. CI verifies offline tests and package compilation; AKShare live access remains an optional manual smoke path so default tests never depend on real network availability.

**Tech Stack:** Python 3.12 in GitHub Actions, pytest, stdlib `compileall`, existing `FundCache` SQLite cache, existing `AkshareProvider`.

---

## Boundaries

- Do not add Web, MCP, LLM, LangGraph, broker integration, or trading execution.
- Do not add TiantianFundProvider in this step.
- Do not make default tests depend on AKShare, internet access, or live finance APIs.
- Do not claim AKShare smoke success unless the command actually runs with real `akshare` installed.
- Keep `source/as_of/updated_at/expires_at/stale` visible in Markdown/HTML reports.

## Phase 2B-0: Repository Hygiene and CI

### Task 1: Clean macOS artifacts

**Files:**
- Delete local untracked `.DS_Store`
- Delete local untracked `docs/.DS_Store`
- Modify: `.gitignore`

**Steps:**

1. Remove the two untracked `.DS_Store` files from the workspace.
2. Add `.DS_Store` to `.gitignore`.
3. Run `git status --short` and confirm the artifact files no longer appear.
4. Commit with `ci: add python verification workflow` or equivalent infra message.

**Acceptance:**

- `.DS_Store` is ignored going forward.
- No `.DS_Store` file is tracked.

### Task 2: Add GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

**Required commands in CI:**

```bash
python -m pytest -q
python -m compileall -q fund_agent
```

**Acceptance:**

- CI runs on pull requests.
- CI runs on pushes to `main`.
- CI does not install AKShare or call live network APIs.

## Phase 2B-1: AKShare Live Smoke Preparation

### Task 3: Keep offline test coverage as default

**Files:**
- Existing: `tests/test_live_provider.py`
- Existing: `tests/test_cache_fallback.py`

**Acceptance:**

- Mock AKShare tests cover field mapping, bad-row isolation, cache write, and cache fallback.
- `python -m pytest -q` passes without `akshare` installed.

### Task 4: Manual AKShare smoke command

Use this command only when `akshare` is installed and network access is available:

```bash
python -m fund_agent.cli daily --provider akshare --watchlist-file configs/watchlist.yaml --portfolio-config configs/portfolio.yaml --output-dir outputs
```

**Expected successful outputs:**

- `outputs/fund_agent_report.md`
- `outputs/fund_agent_report.html`
- `outputs/snapshots/YYYY-MM-DD.json`
- `data/cache/funds.sqlite`

**Success criteria:**

- Command exits with status 0.
- Report includes `## 数据来源与新鲜度`.
- At least one AKShare-backed fund record is written to cache.
- Snapshot is written for the run date.

**Failure handling:**

- If `akshare` is not installed, do not mark smoke as successful.
- If AKShare changes field names, add or adjust mapping tests first, then update `_fund_from_akshare_row`.
- If live fetch fails after cache exists, fallback should generate a report and mark stale/fallback metadata.
- If both live fetch and cache are unavailable, CLI should exit non-zero with a clear provider error.

## Next Provider Health Tasks

1. Add provider-health metadata such as live row count, skipped row count, and cache write count.
2. Add structured warnings for live fallback, empty live response, and all-watchlist-missing results.
3. Add an optional local smoke helper command or documented script that prints AKShare version and provider summary.
4. Expand AKShare mapping coverage only after observing real smoke output.
5. Keep TiantianFundProvider deferred until AKShare smoke is stable.
