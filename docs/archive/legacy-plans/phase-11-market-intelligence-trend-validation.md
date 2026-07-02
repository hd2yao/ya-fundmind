# Phase 11 Market Intelligence Trend Validation

## 目标

Phase 11 在 Market Intelligence v1 的基础上增加两件事：

- 每次 `market-scan` 固化一份 market snapshot，作为后续趋势判断的真实历史输入。
- 新增 `market-trend`，只基于已经存在的 market snapshots 统计主题/板块趋势。

本阶段仍然只做市场观察和证据积累，不修改主评分、不修改主风险、不输出买卖建议。

## Market Snapshot

`market-scan` 每次成功后会写入：

- `outputs/market/snapshots/YYYY-MM-DD.json`
- `outputs/runs/YYYY-MM-DD/market_snapshot.json`

同一天重复运行可以覆盖同一天 snapshot。`as_of` 来自命令参数或当天日期，`generated_at` 保留实际生成时间。

snapshot 包含：

- `schema_version`
- `generated_at`
- `as_of`
- `source`
- `provider`
- `run_type`
- `total_funds`
- `total_etfs`
- `theme_count`
- `hot_theme_count`
- `data_quality_grade`
- `theme_rankings`
- `hot_theme_candidates`
- `insufficient_sample_themes`
- `data_quality_summary`
- `warnings`
- `not_production_model=true`

这些 snapshot 是 Market Intelligence 观察证据，不是主模型证据。

## Market Trend

运行方式：

```bash
python -m fund_agent.cli market-trend \
  --market-dir outputs/market \
  --output-dir outputs \
  --days 30 \
  --min-snapshots 3
```

输出：

- `outputs/market/market_trend_report.json`
- `outputs/market/market_trend_summary.md`
- `outputs/market/theme_trend_rankings.json`

如果当天 run bundle 已存在，也会写入：

- `outputs/runs/YYYY-MM-DD/market_trend_report.json`
- `outputs/runs/YYYY-MM-DD/market_trend_summary.md`

## 趋势统计

`market-trend` 统计：

- 主题排名变化
- 样本量变化
- 持续热门主题
- 新增热门主题
- 消失热门主题
- 数据质量趋势

如果 snapshot 数量少于 `--min-snapshots`，`enough_market_history=false`，命令仍返回成功。这个状态只表示趋势样本不足，不表示 daily ops、dashboard 或 market-scan 失败。

## Daily/Weekly Ops

当 `ENABLE_MARKET_INTELLIGENCE=true`：

- `scripts/run_daily_ops.sh` 会运行 `market-scan`，再尝试运行 `market-trend`。
- `scripts/run_weekly_ops.sh` 会运行 `weekly-research` 后尝试运行 `market-trend`，再刷新 dashboard、long horizon 和 ops-status。

`market-trend` 样本不足或失败会记录 warning，但不会中断 daily/weekly 主流程。

## Dashboard 和 Ops Status

`outputs/dashboard/market.html` 会展示：

- Market Intelligence 当日横截面
- Market Trend Summary
- snapshots_processed
- enough_market_history
- persistent_hot_themes
- new_hot_themes
- rising_themes
- falling_themes
- data_quality_trend
- warnings

`outputs/latest_summary.md` 和 `outputs/ops_status.json` 会展示 Market Intelligence 与 Market Trend 的运行状态。

## 边界

- 不做 historical backfill。
- 不伪造历史 snapshot。
- 不接入新闻、公告、舆情。
- 不接入主评分。
- 不接入主风险。
- 不改变 daily 默认 provider 代码逻辑。
- 不做真实交易。
- 不承诺收益。

## 下一步建议

连续积累真实 market snapshots 后，再做趋势可信度审查：

- 检查至少 3 个有效 market snapshots 后的趋势稳定性。
- 检查主题样本量是否足够。
- 检查数据质量是否长期 warning/degraded。
- 人工确认主题分类是否符合预期。
- 通过审查后，仍先进入实验层，不直接进入主评分/主风险。
