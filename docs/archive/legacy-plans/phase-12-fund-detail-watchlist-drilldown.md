# Phase 12 Fund Detail & Watchlist Drilldown

## Phase 12 目标

Phase 12 adds a Fund Detail and Watchlist Drilldown layer. It lets the dashboard move from market-level observation into per-fund diagnostics for the current watchlist.

This phase does not change the main score, main risk logic, daily default provider behavior, watchlist contents, portfolio contents, or report conclusions.

## 为什么需要 Fund Detail

Market Intelligence can show broad themes and trend candidates, but it does not answer per-fund questions:

- what each watchlist fund looks like today;
- which theme rules it matched;
- where it sits inside its primary theme;
- which return windows are present or missing;
- whether signal candidates or manual review queues reference it;
- which data fields require confirmation.

Fund Detail fills that diagnostic gap.

## 与 Market Intelligence 的关系

Fund Detail reads existing artifacts:

- `outputs/market/market_intelligence_report.json`
- `outputs/market/market_fund_candidates.json`
- `outputs/market/market_trend_report.json`
- `outputs/fund_agent_report.json`
- `outputs/signal_candidates.json`
- `outputs/manual_review_queue.json`
- `outputs/manual_review_state.json`
- optional local cache rows

It does not fetch live network data.

## 与主评分/主风险的边界

Fund Detail is an observation and diagnostic layer only.

It can say:

- data is missing;
- NAV history is incomplete;
- theme sample is small;
- the fund is worth continued observation;
- a fund is not in the main score or main risk path.

It must not:

- modify `ScoredFund`;
- modify `RiskIssue`;
- change `fund_agent_report.json` conclusions;
- create trading instructions;
- promise returns.

## fund-detail CLI

Single fund:

```bash
python -m fund_agent.cli fund-detail \
  --code 021511 \
  --output-dir outputs
```

Multiple funds:

```bash
python -m fund_agent.cli fund-detail \
  --codes 021511,021580,011452 \
  --output-dir outputs
```

Outputs:

- `outputs/fund_details/fund_detail_021511.json`
- `outputs/fund_details/fund_detail_021511.md`
- `outputs/fund_details/watchlist_fund_details.json` for multi-code mode
- `outputs/fund_details/watchlist_fund_details.md` for multi-code mode

## watchlist-detail CLI

```bash
python -m fund_agent.cli watchlist-detail \
  --watchlist-file configs/watchlist.yaml \
  --output-dir outputs
```

The command reads all watchlist codes and writes:

- `outputs/fund_details/watchlist_fund_details.json`
- `outputs/fund_details/watchlist_fund_details.md`

If `outputs/runs/YYYY-MM-DD` exists for the detected `as_of`, the watchlist detail files are also copied into:

- `outputs/runs/YYYY-MM-DD/fund_details/watchlist_fund_details.json`
- `outputs/runs/YYYY-MM-DD/fund_details/watchlist_fund_details.md`

## fund_detail_XXXXXX.json 字段

Each `FundDetailView` contains:

- fund identity: `code`, `name`, `fund_type`, `source`, `as_of`;
- scope flags: `is_watchlist`, `is_portfolio`;
- theme fields: `themes`, `primary_theme`, `theme_confidence`;
- fund fields: `price`, `nav`, `scale`, `fund_company`, `fund_manager`, `rating`;
- return windows: `1w`, `1m`, `3m`, `6m`, `1y`;
- `nav_history_summary` if available;
- `market_rank_context`;
- `signal_context`;
- `data_quality_grade`;
- `missing_fields`;
- `data_quality_warnings`;
- `not_production_model=true`.

## watchlist_fund_details.json 字段

The watchlist summary contains:

- `schema_version`;
- `generated_at`;
- `as_of`;
- `detail_count`;
- `missing_count`;
- `warning_count`;
- `fund_details`;
- `not_production_model=true`;
- `main_score_changed=false`;
- `main_risk_changed=false`.

## dashboard/funds.html

`generate-evidence-dashboard` now writes:

- `outputs/dashboard/funds.html`
- optional single-fund pages under `outputs/dashboard/funds/{code}.html`

If fund detail artifacts are absent, the page shows `Fund Detail 尚未运行` and does not fail dashboard generation.

## Daily Ops

When `ENABLE_MARKET_INTELLIGENCE=true`, daily ops now tries:

```bash
python -m fund_agent.cli watchlist-detail \
  --watchlist-file configs/watchlist.yaml \
  --portfolio-config configs/portfolio.yaml \
  --output-dir outputs
```

If this step fails, daily ops records a warning and continues.

## 为什么第一版不做新闻/公告/舆情

News and sentiment require source reliability, timestamp alignment, and evidence attribution. This phase only reads local structured artifacts and cache data.

## 为什么第一版不做 historical backfill

Backfill requires true historical inputs. Creating old folders from current data would pollute trend and stability evidence.

## 为什么不输出买卖建议

Fund Detail is diagnostic. It helps inspect data coverage and context, but it does not validate allocation, timing, or trade execution decisions.

## 后续 Phase 13 建议

- Improve fund detail HTML styling and filtering.
- Add explicit peer comparison tables for primary themes.
- Add cache-backed Tiantian detail coverage checks.
- Add optional data-quality gates before any future score/risk integration review.
