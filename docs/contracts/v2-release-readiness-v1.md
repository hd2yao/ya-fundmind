# V2 Release Readiness Contract v1

## 用途

`outputs/release/v2_release_readiness.json` 是 YA FundMind OS V2 发布门禁的机器可读结果。它只读取既有 outputs，证明 contract、性能预算、研究边界和至少三个不同日期的真实 daily run 是否满足发布条件。

该文件不参与主评分、主风险、daily 计算或交易；删除后可重新生成。

## Schema

- `schema_version`: 必填，当前为 `1.0`。
- `generated_at`: 必填，UTC ISO 8601。
- `generator`: 必填，固定为 `fund_agent`。
- `release_target`: 必填，例如 `v2.0.0`。
- `status`: 必填，`pass` 或 `fail`。
- `minimum_valid_runs`: 必填，最小真实 run 数量。
- `valid_run_count`: 必填，实际通过门禁的不同日期 run 数量。
- `observed_run_dates`: 必填，通过门禁的 ISO 日期列表。
- `run_observations`: 必填，每个历史 run 的状态、provider、live rows、contract 和排除原因。
- `contract_summary`: 必填，已检查 contract 数量和失败项。
- `performance`: 必填，Catalog、market Query、deterministic Answer 的测量值、预算和状态。
- `boundaries`: 必填，研究只读边界必须为：
  - `not_production_model=true`
  - `main_score_changed=false`
  - `main_risk_changed=false`
  - `trading_enabled=false`
- `blockers`: 必填，阻止发布的结构化原因。
- `warnings`: 必填，不阻止发布但需要记录的观察项。

## 真实 Run 规则

一个 run 只有同时满足以下条件才计入：

- 目录名和 summary `as_of` 是同一 ISO 日期。
- `daily_research_summary.json`、`run_metadata.json` 存在且状态成功。
- `daily` 和 `validate_contract` step 成功。
- `fund_agent_report.json`、`snapshot.json`、`provider_trace.json` 存在且各自 contract 通过。
- 数据质量为 `normal` 或 `warning`，不能是 `degraded/critical`。
- provider 不是 fixture/demo/synthetic，`live_row_count > 0`。
- 没有 fallback、critical provider warning 或 missing artifacts。
- 主评分、主风险和 research-only 边界未改变。

不同日期才能计为不同 run；重复执行同一天不能增加数量。历史真实 run 可以用于 RC 兼容观察，但不能复制、改写或伪造。

## 兼容策略

- v1 reader 必须忽略未知字段。
- 新增可选字段可保持 schema `1.x` 兼容。
- 删除、重命名必填字段或改变字段语义需要 major schema。
- 旧系统没有该文件属于“尚未执行 V2 release gate”，不影响 V1 daily/weekly。

## 下游读取建议

- 自动化只读取本 JSON，不解析 release Markdown。
- 只有 `status=pass` 且 `blockers=[]` 才可进入 Final 发布。
- `warning` run 可以保留作为真实质量事件；不得隐藏或改写成 normal。
- scheduler/launchctl 是本机外部状态，仍需与该 JSON 一起人工核对。

## 示例

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-07-13T00:00:00+00:00",
  "generator": "fund_agent",
  "release_target": "v2.0.0",
  "status": "pass",
  "minimum_valid_runs": 3,
  "valid_run_count": 3,
  "observed_run_dates": ["2026-07-10", "2026-07-11", "2026-07-12"],
  "run_observations": [],
  "contract_summary": {"ok": true, "files_checked": 6, "failures": []},
  "performance": {"within_budget": true, "measurements_ms": {}, "budgets_ms": {}},
  "boundaries": {
    "not_production_model": true,
    "main_score_changed": false,
    "main_risk_changed": false,
    "trading_enabled": false
  },
  "blockers": [],
  "warnings": []
}
```

## 校验

```bash
python -m fund_agent.cli validate-contract --release-readiness outputs/release/v2_release_readiness.json
python -m fund_agent.cli validate-contract --output-dir outputs
```
