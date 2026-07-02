# Evidence Collection Operating Plan

## 目的

Daily ops 连续运行不是为了立刻生成交易建议，而是为了积累可复查的本地研究证据。

每次运行都会写入一个 `outputs/runs/YYYY-MM-DD/` run bundle，用来观察：

- 数据源是否稳定；
- provider 是否经常 fallback 或 stale；
- 自选池研究分数和估值是否剧烈波动；
- candidate signal 是否持续出现；
- experiment scoring 是否长期没有过度敏感；
- manual review queue 是否有反复出现的问题。

这些证据只用于后续研究和人工审核，不会自动修改主评分、主风险或交易动作。

## 当前状态

截至最近一次 daily ops：

- `runs_processed`: 4
- `minimum_required_runs`: 20
- `enough_history`: false
- `blockers`: `insufficient_history`
- `data_quality_consistency`: 最近 run 均为 `normal`
- `recommend_main_model`: `no`

当前系统已经可以稳定生成：

- `outputs/fund_agent_report.json`
- `outputs/fund_agent_report.html`
- `outputs/snapshots/YYYY-MM-DD.json`
- `outputs/traces/provider-YYYY-MM-DD.json`
- `outputs/runs/YYYY-MM-DD/`
- `outputs/weekly_research_summary.json`
- `outputs/long_horizon_stability.json`
- `outputs/latest_summary.md`

## 收数条件

一次 run 计入有效历史样本，至少需要满足：

- `daily_status = success`
- `data_quality_grade` 不应长期为 `degraded`
- `provider_health.fallback_used = false` 或 fallback 原因可解释
- `provider_warnings` 不应长期出现 critical warning
- `validate-contract` 通过
- `outputs/runs/YYYY-MM-DD/` 中关键 JSON artifact 存在

关键 artifact 包括：

- `fund_agent_report.json`
- `snapshot.json`
- `provider_trace.json`
- `signal_candidates.json`
- `experiment_scoring_report.json`
- `experiment_baseline_comparison.json`
- `experiment_config_sensitivity.json`
- `signal_readiness_review.json`
- `manual_review_queue.json`
- `daily_research_summary.json`

## 需要跑多久

当前长周期稳定性门槛来自 `fund_agent.long_horizon.evaluate_long_horizon_stability()`：

- 默认观察窗口：最近 30 天；
- 最少有效 run 数：20；
- 少于 20 个有效 run 时，`enough_history=false`；
- 少于 20 个有效 run 时，所有非展示类 signal 都只能停留在 `needs_more_data` 或更保守状态。

实际操作建议：

- 短期检查：连续 7 天，用于看 daily ops 是否稳定；
- 第一阶段样本：至少 20 个有效交易日 run，用于解除 `insufficient_history`；
- 更稳妥样本：30 个自然日窗口内尽量覆盖 20 个以上有效交易日；
- 如果中间出现 provider 大面积 fallback、critical warning、contract failure，需要从修复后重新观察稳定性。

## 当前还缺什么

当前 daily ops 收集的是自选池研究证据，不是全市场板块轮动证据。

已经有：

- AKShare 基金/ETF live 数据；
- 自选池筛选；
- 持仓风险；
- provider health；
- snapshots；
- signal candidate；
- experiment scoring；
- long-horizon stability。

还没有：

- 全市场基金/ETF 板块归类；
- 板块热度排名；
- 板块历史增长趋势；
- 新闻、公告、政策、研报或舆情数据源；
- 新闻/公告到板块的证据映射；
- 板块观点的数据验证；
- 基于板块结论的主评分或主风险接入。

## 达标条件

进入下一阶段前，至少需要看到：

- `runs_processed >= 20`
- `enough_history = true`
- `blockers` 不包含 `insufficient_history`
- 最近 run 的 `data_quality_grade` 主要为 `normal`
- critical provider warning 不反复出现
- config sensitivity 没有长期 unstable
- candidate signal 的 eligible rate 达到门槛，当前长周期规则默认要求不低于 `0.6`
- manual review state 对方向给出明确结论

这些条件只表示可以进入更深入的实验阶段，不表示可以直接改变主评分或主风险。

## 跑完之后做什么

达到 20 个以上有效 run 后，下一步不是直接改主模型，而是做一次 review gate：

1. 读取 `outputs/long_horizon_stability.json`。
2. 读取 `outputs/weekly_research_summary.json`。
3. 检查 repeated blockers 和 exclusion reasons。
4. 检查 signal candidate 是否稳定。
5. 检查 experiment scoring 是否长期 applied signal 为 0。
6. 检查 manual review queue 是否仍然主要是 `needs_data`。
7. 生成一次人工审核结论。

如果仍然没有可用 signal，则继续收数或补数据源。

如果有稳定 signal，只能进入独立实验 PR，要求：

- 新增主评分回归测试；
- 新增主风险回归测试；
- 新增 stale/fallback/degraded 数据测试；
- 新增 baseline comparison；
- 明确不改变历史报告 contract；
- 人工审核通过后才考虑主模型接入。

## 下一阶段建议

在 daily ops 已经能稳定跑的前提下，下一阶段建议优先做 `Market Intelligence`，但仍然不接主评分和主风险：

- 建立基金/ETF 板块和主题分类；
- 对全量 AKShare 基金/ETF 做热度扫描；
- 统计 1w/1m/3m/6m/1y 收益、上涨广度和样本数；
- 加入新闻、公告、政策或官方消息数据源；
- 建立新闻/公告到板块的 evidence mapping；
- 输出独立的 `market_intelligence_report.json` 和 HTML 页面；
- 将板块观点与历史数据交叉验证。

这个阶段的目标是回答“近期哪些板块更强，以及证据是否支持这个判断”，仍然不产生买卖指令。

## 日常操作

手动运行：

```bash
PROVIDER=akshare OUTPUT_DIR=outputs scripts/run_daily_ops.sh
```

查看状态：

```bash
cat outputs/latest_summary.md
open outputs/fund_agent_report.html
open outputs/dashboard/index.html
```

检查长周期门槛：

```bash
cat outputs/long_horizon_stability.json
```

当 `enough_history=true` 后，再进行人工 review gate。
