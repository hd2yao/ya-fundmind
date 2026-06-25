# Phase 2F Tiantian Diagnostics + Signal Experiment

## Phase 2F 目标

Phase 2F 在 Phase 2E 的 Tiantian enrichment、NAV windows 和 `--allow-cache` 基础上，补齐诊断和实验能力。

本阶段完成：

- 新增 Tiantian cache fallback 诊断命令。
- NAV windows 从自然日近似改为有效 NAV 点窗口。
- 新增手动 `smoke-tiantian` CI job。
- 新增 Tiantian signals 实验命令，用于评估未来进入评分/风险的候选资格。

本阶段仍不做：

- 不接入主评分模型。
- 不接入主风险逻辑。
- 不改变 daily 默认 provider。
- 不做 Web、MCP、LLM、LangGraph。
- 不做真实交易。
- 不承诺收益。

## NAV 交易日窗口定义

窗口按有效 NAV 点数量截取，而不是自然日：

- `1m`: 最近 20 个有效 NAV 点
- `3m`: 最近 60 个有效 NAV 点
- `6m`: 最近 120 个有效 NAV 点
- `1y`: 最近 240 个有效 NAV 点
- `all`: 全部有效 NAV 点

每个窗口 metadata 包含：

- `required_points`
- `actual_points`
- `window_mode: "nav_points"`
- `annualized_return_unstable`
- `annualized_return_note`，仅短样本时出现

样本不足时：

- 0 到 1 个有效点：`degraded`
- 2 个以上但少于 required points：`warning`

这些指标仍只用于观察，不进入评分或风险主逻辑。

## diagnose-tiantian-cache

命令：

```bash
python -m fund_agent.cli diagnose-tiantian-cache --code 510300 --output-dir outputs
```

可指定 cache：

```bash
python -m fund_agent.cli diagnose-tiantian-cache --code 510300 --cache-file data/cache/funds.sqlite --output-dir outputs
```

行为：

- 不访问真实网络。
- 只读取 SQLite cache。
- 写入 `outputs/tiantian_cache_diagnostics.json`。
- cache miss 返回清晰信息和非 0 exit code。

输出字段：

```json
{
  "code": "510300",
  "detail_cache_status": "hit",
  "nav_cache_status": "hit",
  "detail_source": "cache:tiantian",
  "nav_source": "cache:tiantian",
  "nav_points_count": 240,
  "latest_nav_date": "2026-06-23",
  "available_windows": ["1m", "3m", "6m", "1y", "all"],
  "stale": false,
  "warnings": []
}
```

## experiment-tiantian-signals

命令：

```bash
python -m fund_agent.cli experiment-tiantian-signals --input outputs/fund_agent_report.json --output outputs/tiantian_signal_experiment.json
```

功能：

- 读取 JSON report 中的 `fund_details` 和 `nav_history_summary`。
- 根据 `docs/contracts/scoring-risk-input-contract.md` 评估未来可进入评分/风险候选层的信号。
- 不修改主 score。
- 不修改主 `risk_issues`。

输出字段：

- `eligible_signals`
- `excluded_signals`
- `exclusion_reasons`
- `display_only_fields`
- `required_regression_tests`
- `warnings`

排除规则：

- `degraded` window 必须 excluded。
- `warning` window 默认 excluded。
- `annualized_return_unstable` 必须 excluded。
- 样本点不足必须 excluded。
- missing Tiantian fields 不得变成正向信号。
- `fund_manager`、`fund_company`、`inception_date` 只能 display-only。

## 手动 smoke-tiantian CI job

CI 默认行为不变：

- PR 不运行真实 Tiantian。
- push 不运行真实 Tiantian。

手动触发：

- workflow_dispatch 设置 `run_tiantian_smoke=true`。
- 读取 `TIANTIAN_API_BASE_URL` secret。
- 如果 secret 未配置，job 输出清晰 skip 信息并 exit 0。
- 如果 secret 已配置，运行：

```bash
python -m fund_agent.cli smoke-tiantian --code 510300 --output-dir outputs
python -m fund_agent.cli validate-contract --output-dir outputs
```

## 为什么仍不修改主评分/主风险

Phase 2F 的 signal experiment 是离线评估工具，不是模型接入。它只回答“哪些 Tiantian 字段满足未来候选条件”，不改变已有候选排序、估值、组合风险或报告主结论。

真正接入主评分/风险前，需要：

- 明确每个字段的权重和方向。
- 明确缺失字段默认行为。
- 明确 stale cache 的排除策略。
- 建立评分/风险前后对照测试。
- 更新 snapshot delta 的解释。
- 做独立 PR，而不是混入 enrichment 稳定化。

## 验证命令

```bash
python -m pytest -q
python -m compileall -q fund_agent
python -m fund_agent.cli demo --output-dir outputs --as-of 2026-06-23
python -m fund_agent.cli daily --provider fixture --watchlist-file configs/watchlist.yaml --portfolio-config configs/portfolio.yaml --output-dir outputs --as-of 2026-06-23
python -m fund_agent.cli validate-contract --output-dir outputs
```

可选本地诊断：

```bash
python -m fund_agent.cli diagnose-tiantian-cache --code 510300 --output-dir outputs
```

可选实验：

```bash
python -m fund_agent.cli experiment-tiantian-signals --input outputs/fund_agent_report.json --output outputs/tiantian_signal_experiment.json
```

真实 Tiantian smoke 仅在配置 `TIANTIAN_API_BASE_URL` 后运行：

```bash
python -m fund_agent.cli smoke-tiantian --code 510300 --output-dir outputs
```

## Phase 2G 建议

- 增加交易日窗口的实际交易日历支持。
- 为 signal experiment 增加历史批量评估模式。
- 增加 Tiantian 数据质量趋势 snapshot，但仍不接主评分。
- 在单独实验分支设计评分/风险模型变更草案。
