# Phase 3 Research Signal Candidate Layer

## Phase 3 目标

Phase 3 在现有 AKShare、Tiantian、JSON report、snapshot、provider trace 和 `experiment-tiantian-signals` 基础上，建立投研信号候选层。

本阶段只生成候选信号和实验报告：

- 不修改主评分模型。
- 不修改主风险逻辑。
- 不改变 daily 默认 provider。
- 不做 Web、MCP、LLM、LangGraph。
- 不做真实交易。
- 不承诺收益。

## SignalCandidate 字段

`SignalCandidate` 描述一个未来可能进入评分或风险的候选信号：

- `signal_id`: 稳定信号 ID。
- `source`: 数据来源，例如 `tiantian` 或 `akshare`。
- `code`: 基金代码。
- `category`: 信号类别。
- `value`: 信号值。
- `direction`: 未来可能的方向解释，例如 `positive`、`negative`、`neutral`。
- `quality_grade`: `normal`、`warning`、`degraded` 等质量标记。
- `eligible`: 是否满足候选资格。
- `excluded_reason`: 被排除原因。
- `evidence`: 简要证据说明。
- `metadata`: 额外上下文。

类别包括：

- `return`
- `drawdown`
- `volatility`
- `liquidity`
- `rating`
- `data_quality`
- `display_only`

## Tiantian 信号规则

Tiantian NAV windows:

- `normal` window 且满足 `required_points` 才可生成 eligible candidate。
- `degraded` window 必须 excluded。
- `warning` window 默认 excluded。
- `annualized_return_unstable` 必须 excluded。
- 样本点不足必须 excluded。

Tiantian detail:

- `scale` 和 `rating` 只进入 candidate layer，不进入主 score。
- `fund_manager`、`fund_company`、`inception_date` 只能 display-only。
- missing Tiantian fields 不得变成正向信号。

## AKShare 信号规则

AKShare/fixture 已有字段只做轻量候选：

- fund category: display-only。
- fund scale: 如果存在，可作为 liquidity candidate。
- recent returns: 如果存在，可作为 return candidate。
- valuation confidence: 可作为 data quality candidate。
- provider fallback/stale/warnings: 可作为 data quality candidate。

字段不存在时不硬造 signal。

## 命令

生成信号候选：

```bash
python -m fund_agent.cli generate-signal-candidates --input outputs/fund_agent_report.json --output outputs/signal_candidates.json
```

继续兼容 Tiantian 实验命令：

```bash
python -m fund_agent.cli experiment-tiantian-signals --input outputs/fund_agent_report.json --output outputs/tiantian_signal_experiment.json
```

批量实验：

```bash
python -m fund_agent.cli batch-signal-experiment --input-dir outputs/history --output outputs/signal_batch_report.json
```

或读取 snapshots：

```bash
python -m fund_agent.cli batch-signal-experiment --snapshot-dir outputs/snapshots --output outputs/signal_batch_report.json
```

## signal_candidates.json 示例

```json
{
  "eligible_signals": [
    {
      "signal_id": "tiantian:510300:return:1m:total_return",
      "source": "tiantian",
      "code": "510300",
      "category": "return",
      "value": 1.2,
      "direction": "positive",
      "quality_grade": "normal",
      "eligible": true
    }
  ],
  "excluded_signals": [],
  "display_only_signals": [],
  "summary": {
    "total_signals": 1,
    "eligible_count": 1,
    "excluded_count": 0,
    "display_only_count": 0
  }
}
```

## 为什么不直接接主评分/主风险

候选信号只是“可能值得进入模型的原料”。主评分和主风险需要独立设计：

- 权重和方向必须可解释。
- 缺失字段和 stale cache 必须有明确默认行为。
- 必须有基线对照测试。
- 必须验证 snapshot delta 和报告解释不会误导。

Phase 3 只输出候选和实验报告，不改变主 score、主 `risk_issues` 或报告主结论。

## 进入评分/风险前条件

真正接入模型前至少需要：

- 完整字段契约。
- 缺失/过期/降级数据处理策略。
- 评分前后对照快照。
- AKShare/fixture daily 回归稳定。
- Tiantian live/cache fallback 回归稳定。
- 人工确认 signal direction 和权重。

## Phase 3B 建议

- 增加 signal candidate 的历史稳定性统计。
- 将 signal_quality_summary 自动写入 snapshot。
- 增加候选信号解释报告，但仍不改变主模型。
- 在独立实验分支设计评分/风险接入草案。
