# Fund ETF Agent Design

## Goal

Build a first usable version of a local fund and ETF investment research system. It should help a user screen China public funds, ETFs, LOFs, ETF feeder funds, and QDII products; analyze an optional portfolio; produce a Markdown/HTML daily report; and keep all outputs framed as research assistance, not investment advice or trade execution.

## Scope

The first version covers:

- Open-ended public funds from AKShare.
- Exchange-traded ETFs and LOFs.
- ETF feeder funds.
- QDII and cross-border ETFs when source data is available.
- Local portfolio files with fund code, name, shares, cost NAV, buy date, target weight, and notes.
- Local command line workflows.

The first version does not cover:

- Individual stock recommendations.
- Brokerage integration or automatic order execution.
- Intraday high-frequency trading.
- User accounts, authentication, or hosted multi-user deployment.
- Guaranteed return language.

## Reference Lessons

The design borrows selectively from the researched projects:

- `ZhuLinsen/daily_stock_analysis`: daily workflow, local/web report pattern, data degradation, notifications as a later extension.
- `Deng-XueCheng/fund-investment-assistant`: fund-first scoring, anti-chasing, fee-aware portfolio advice, audit-friendly reasoning.
- `hkwuks/Fund-Valuation-Framework`: fund valuation types for ETFs, ETF feeders, index funds, QDII, active funds, and benchmark-only fallback.
- `oujingzhou/openfr`, `24mlight/A_Share_investment_Agent`, and `virattt/ai-hedge-fund`: multi-agent flow with analyst signals, risk manager, and portfolio manager.
- `muxuuu/serenity-skill`: evidence labels, failure conditions, and clear risk boundary.
- `belos-street/stock-analytics-skill` and `rkiding/awesome-finance-skills`: skill/tool-friendly local command shape.

## Architecture

The MVP is a Python package plus CLI:

```text
CLI
  -> data providers
  -> cache
  -> scoring engine
  -> valuation engine
  -> portfolio/risk engine
  -> agent-style orchestrator
  -> report renderer
```

The system stays deterministic where possible. The first version uses structured "agent" classes rather than requiring an LLM API key. This gives a visible working result without secrets and leaves room to add LLM commentary later through an adapter.

## Core Components

### Data Layer

Use a provider abstraction so network-backed providers and fixtures can share one interface.

- `AkshareProvider`: optional live data source.
- `FixtureProvider`: deterministic fallback for tests and demo.
- `CacheStore`: JSON/CSV files under `data/cache/`, with TTL and stale-data warnings.

Primary fields:

- code, name, category, latest NAV, NAV date.
- 1w, 1m, 3m, 6m, 1y, 2y, 3y returns.
- daily return, scale, manager, fee fields when available.
- ETF price, premium/discount, benchmark/index mapping when available.

### Scoring Engine

The default score is anti-chasing and fund-specific:

- Return quality: weighted multi-period returns with negative-return penalty.
- Trend consistency: penalize sprint-like one-month moves that are not supported by longer periods.
- Momentum confirmation: reward consistent 1m/3m/6m/1y positive performance.
- Risk adjustment: approximate Sharpe from multi-period return stability.
- Liquidity/scale guard: penalize too-small or unknown-scale products.

The output is a research priority score, not a buy/sell command.

### Valuation Engine

Classify fund products before estimating:

- `etf_price`: exchange-traded ETF/LOF, use current market price fields if present.
- `index_based`: broad/sector ETF or index fund, use benchmark/index return if known.
- `feeder`: ETF feeder fund, estimate through mapped target ETF when known.
- `qdii_proxy`: QDII/cross-border ETF, use proxy index/ETF if mapped.
- `nav_only`: open-ended active fund where only latest NAV/history is available.
- `unsupported`: insufficient data.

Each valuation result includes a confidence label and missing data notes.

### Portfolio And Risk

Portfolio analysis is optional. When a portfolio file is present, the system computes:

- current value and unrealized return from latest NAV/price.
- target-weight drift.
- single-fund concentration.
- category concentration.
- stale data warnings.
- A/C class and short holding-period fee notes where naming and holding period make this possible.

The recommendation surface is deliberately phrased as "observe/add candidate/reduce candidate/rebalance candidate" rather than "buy/sell now".

### Agent-Style Orchestration

First version agents are deterministic classes:

- `DataAgent`: resolves and normalizes fund/ETF data.
- `ScreeningAgent`: ranks research candidates.
- `ValuationAgent`: classifies valuation method and confidence.
- `RiskAgent`: checks concentration, stale data, drawdown proxy, and data gaps.
- `PortfolioAgent`: combines screening, valuation, and risk into action candidates.
- `ReportAgent`: renders evidence-aware Markdown and HTML reports.

This structure can later be wrapped by LangGraph or exposed through MCP without changing the core domain logic.

### CLI Workflows

Planned commands:

- `fund-agent demo`: run entirely from fixtures and generate a sample report.
- `fund-agent screen`: screen funds/ETFs from live provider if installed, otherwise fixtures.
- `fund-agent portfolio --file data/portfolio.example.json`: analyze local holdings.

The demo command is the first visible effect for this turn.

## Error Handling

- Live provider failures fall back to cache when available.
- Missing optional fields are represented as warnings, not crashes.
- Stale data is shown in the report.
- Unknown valuation methods degrade to `nav_only` or `unsupported`.
- No secrets are required for the first version.

## Testing

Use pytest with fixture data. Core tests cover:

- scoring rewards stable multi-period strength over sprint-only moves.
- valuation classification for ETF, feeder, QDII, and NAV-only products.
- portfolio drift and concentration warnings.
- report generation includes risk boundary and evidence labels.
- CLI demo writes Markdown and HTML reports.

## Design Self-Review

### Strengths

- Keeps the first version useful without requiring API keys or an LLM.
- Avoids overbuilding a web app before the investment workflow is proven.
- Separates data, scoring, valuation, risk, and reporting, so later MCP/Web/LangGraph integration is straightforward.
- Uses clear risk language and evidence labels from the start.

### Risks

- AKShare and unofficial 天天基金 APIs can change. The provider abstraction and fixture fallback reduce breakage, but live data still needs maintenance.
- ETF feeder and QDII mappings are incomplete in a first version. Unknown products must degrade gracefully.
- Fund scores can be misleading without full holdings and fee data. The report must show missing fields and confidence.
- HTML output will be simple in the first version; polish can come after domain behavior works.

### Rejected Alternatives

- Web-first implementation: more visible but slower to reach a correct investment workflow.
- LLM-first multi-agent framework: impressive output, but needs secrets and makes correctness harder to test.
- Full trading bot: out of scope and unsafe for a research assistant MVP.
