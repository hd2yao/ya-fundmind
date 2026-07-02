# Fund ETF Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a first runnable local fund and ETF research assistant with deterministic demo data, optional live AKShare provider, scoring, valuation, portfolio risk checks, and Markdown/HTML reports.

**Architecture:** Implement a small Python package named `fund_agent`. Keep domain logic pure and testable. The CLI composes providers, scoring, valuation, portfolio analysis, and report rendering.

**Tech Stack:** Python 3.10+, stdlib dataclasses/json/argparse/pathlib, pytest for tests, optional AKShare import behind a provider boundary.

---

### Task 1: Scoring Engine

**Files:**
- Create: `tests/test_scoring.py`
- Create: `fund_agent/models.py`
- Create: `fund_agent/scoring.py`
- Create: `fund_agent/__init__.py`

**Step 1: Write the failing test**

Create tests that assert a stable multi-period fund outranks a sprint-only fund, and that negative long-term returns are penalized.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scoring.py -q`

Expected: FAIL because `fund_agent.scoring` does not exist.

**Step 3: Write minimal implementation**

Add dataclasses for fund records and score breakdowns. Implement `score_fund()` and `rank_funds()` with weighted returns, trend consistency, momentum confirmation, risk adjustment, anti-sprint penalty, and scale penalty.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_scoring.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add fund_agent tests/test_scoring.py
git commit -m "feat: add fund scoring engine"
```

### Task 2: Valuation Classification

**Files:**
- Create: `tests/test_valuation.py`
- Create: `fund_agent/valuation.py`

**Step 1: Write the failing test**

Create tests for ETF, ETF feeder, QDII proxy, NAV-only, and unsupported classification.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_valuation.py -q`

Expected: FAIL because `fund_agent.valuation` does not exist.

**Step 3: Write minimal implementation**

Implement `classify_valuation()` and `estimate_value()` using fund category, exchange-traded flag, target ETF, proxy symbol, latest price, and latest NAV.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_valuation.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add fund_agent/valuation.py tests/test_valuation.py
git commit -m "feat: classify fund valuation methods"
```

### Task 3: Portfolio Risk Analysis

**Files:**
- Create: `tests/test_portfolio.py`
- Create: `fund_agent/portfolio.py`

**Step 1: Write the failing test**

Create tests for position value, target drift, single-fund concentration, and stale valuation warnings.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_portfolio.py -q`

Expected: FAIL because `fund_agent.portfolio` does not exist.

**Step 3: Write minimal implementation**

Add `PortfolioHolding`, `PortfolioPosition`, and `PortfolioSummary`. Implement `analyze_portfolio()`.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_portfolio.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add fund_agent/portfolio.py tests/test_portfolio.py
git commit -m "feat: add portfolio risk analysis"
```

### Task 4: Provider And Fixture Data

**Files:**
- Create: `tests/test_provider.py`
- Create: `fund_agent/providers.py`
- Create: `data/fixtures/funds.json`
- Create: `data/portfolio.example.json`

**Step 1: Write the failing test**

Create tests that fixture provider loads sample funds and an example portfolio without network access.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_provider.py -q`

Expected: FAIL because `fund_agent.providers` does not exist.

**Step 3: Write minimal implementation**

Implement `FixtureProvider` and optional `AkshareProvider` with graceful import errors. Add sample fund and portfolio JSON files.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_provider.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add fund_agent/providers.py data/fixtures/funds.json data/portfolio.example.json tests/test_provider.py
git commit -m "feat: add fund data providers"
```

### Task 5: Agent Orchestration And Reports

**Files:**
- Create: `tests/test_report.py`
- Create: `fund_agent/agents.py`
- Create: `fund_agent/report.py`

**Step 1: Write the failing test**

Create tests that the research run returns ranked candidates, valuation confidence, portfolio warnings, evidence labels, and a risk disclaimer in Markdown and HTML.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report.py -q`

Expected: FAIL because `fund_agent.agents` and `fund_agent.report` do not exist.

**Step 3: Write minimal implementation**

Implement deterministic agent classes and `run_research()`. Implement Markdown and simple HTML rendering.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_report.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add fund_agent/agents.py fund_agent/report.py tests/test_report.py
git commit -m "feat: add research agents and reports"
```

### Task 6: CLI And Documentation

**Files:**
- Create: `tests/test_cli.py`
- Create: `fund_agent/cli.py`
- Create: `pyproject.toml`
- Create: `README.md`

**Step 1: Write the failing test**

Create tests that `fund-agent demo --output-dir <tmp>` writes Markdown and HTML report files.

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py -q`

Expected: FAIL because `fund_agent.cli` does not exist.

**Step 3: Write minimal implementation**

Implement CLI commands: `demo`, `screen`, and `portfolio`. Add package metadata and README run instructions.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add fund_agent/cli.py pyproject.toml README.md tests/test_cli.py
git commit -m "feat: add fund agent CLI"
```

### Task 7: Full Verification And Demo Output

**Files:**
- Create user-facing reports in `outputs/`.

**Step 1: Run full tests**

Run: `python -m pytest -q`

Expected: PASS.

**Step 2: Run CLI demo**

Run: `python -m fund_agent.cli demo --output-dir outputs`

Expected: creates `outputs/fund_agent_report.md` and `outputs/fund_agent_report.html`.

**Step 3: Run focused code review**

Review the full diff for correctness, risk boundary, missing tests, and uncommitted tracked edits.

**Step 4: Commit demo outputs if appropriate**

Keep generated outputs untracked because `outputs/` is ignored. Commit only source/docs changes if any remain.

**Step 5: Report final state**

Run: `git status --short`

Expected: no tracked file edits left uncommitted.
