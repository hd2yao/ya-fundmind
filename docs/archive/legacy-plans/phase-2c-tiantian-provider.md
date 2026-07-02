# Phase 2C TiantianFundProvider

## Phase 2C 目标

Phase 2C 的目标是把 TiantianFundProvider 作为 AKShare 之外的补充数据源接入到本地研究系统中，完成基金详情和历史净值的最小闭环。

本阶段只做：

- 数据接入
- SQLite cache 写入和读取
- provider trace
- JSON report 可选字段
- contract validation 兼容

本阶段不做：

- 不接入评分模型
- 不接入风险指标
- 不改变 daily 默认 provider
- 不做真实交易
- 不承诺收益
- 不引入 Web、MCP、LLM、LangGraph

## TiantianFundProvider 支持字段

### FundDetail

- `code`
- `name`
- `fund_type`
- `fund_company`
- `fund_manager`
- `inception_date`
- `scale`
- `rating`
- `source`
- `as_of`
- `updated_at`
- `metadata`

### FundNavPoint

- `code`
- `date`
- `unit_nav`
- `accumulated_nav`
- `daily_return`
- `source`
- `updated_at`
- `metadata`

字段缺失时使用 `None` 安全降级。历史净值坏行会被跳过，并记录 `skipped_rows` warning，不影响其他行。

## CLI 使用方式

显式补充单只基金详情和历史净值：

```bash
python -m fund_agent.cli enrich-fund --provider tiantian --code 510300 --output-dir outputs
```

可选真实 smoke：

```bash
python -m fund_agent.cli smoke-tiantian --code 510300 --output-dir outputs
```

当前默认实现不会自动访问公网。没有配置 Tiantian client 或兼容服务时，命令会返回清晰错误，不会伪造成功。

如果本地已有 TiantianFundApi 兼容服务，可通过环境变量启用真实 smoke：

```bash
export TIANTIAN_API_BASE_URL=http://127.0.0.1:3000
python -m fund_agent.cli smoke-tiantian --code 510300 --output-dir outputs
```

未设置 `TIANTIAN_API_BASE_URL` 时不会发起真实网络请求。

## Cache 写入说明

Tiantian 数据写入现有 SQLite cache：

- `fund_details`: 保存基金详情 JSON
- `fund_navs`: 保存历史净值点，包括单位净值、累计净值和日涨跌

cache 读取会保留：

- `source`
- `as_of`
- `updated_at`
- `expires_at`
- `stale`

从 cache 读取的 source 使用 `cache:tiantian`。

## Provider Trace 示例

Tiantian trace 遵守 `docs/contracts/provider-trace-v1.md`。

```json
{
  "provider": "tiantian",
  "provider_version": null,
  "live_row_count": 3,
  "mapped_row_count": 3,
  "skipped_row_count": 0,
  "cache_write_count": 3,
  "fallback_used": false,
  "endpoints": [
    {
      "endpoint": "tiantian_fund_detail",
      "success": true,
      "mapped_row_count": 1
    },
    {
      "endpoint": "tiantian_nav_history",
      "success": true,
      "mapped_row_count": 2
    }
  ],
  "warnings": []
}
```

## 与 AKShare 的关系

AKShare 仍是当前 live daily 路径的主要 provider。TiantianFundProvider 只作为显式 enrichment provider 使用，不自动参与 daily 主流程。

Phase 2C 不改变：

- AKShareProvider
- fixture provider
- daily 默认 provider
- 评分模型
- 风险模型

## 为什么本阶段不接入评分和风险

Tiantian 数据首先需要完成稳定的数据契约、cache 和 trace 闭环。基金详情和历史净值对评分/风险有潜在价值，但直接接入会扩大行为变化面，影响现有 MVP 的解释性和可回归性。

因此本阶段先把 Tiantian 数据作为可选补充字段输出：

- JSON report: `fund_details`
- JSON report: `nav_history_summary`
- provider trace: `provider=tiantian`

后续再基于这些稳定输出决定是否进入评分或风险。

## Contract Validation

Phase 2C 新增字段是 v1 JSON report 的可选字段，不改变已有必填字段语义。

验证命令：

```bash
python -m fund_agent.cli validate-contract --output-dir outputs
```

下游 Agent/Skill/Web 应读取 JSON report、provider trace、snapshot，不解析 Markdown。

## Phase 2D 建议

- 完善真实 Tiantian client 的分页、错误分类和可选 smoke CI job。
- 增加基金详情字段的数据质量规则。
- 增加历史净值统计摘要，但仍先不接入评分。
- 在稳定后再评估是否把规模、评级、经理信息纳入评分模型。
