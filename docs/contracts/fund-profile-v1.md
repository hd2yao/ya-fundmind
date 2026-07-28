# Fund Profile v1 Contract

## 用途

`Fund Profile v1` 定义 V3 M2 的基金产品资料机器可读契约。它服务于本地 Product API、`fetch-fund-profile` artifact、SQLite cache 和 trace；不替代既有 `fund_agent_report.json`、snapshot 或 Provider Trace v1。

## 版本与兼容性

- `schema_version`：`1.0`。
- 只允许新增可选字段；字段删除、重命名或语义改变必须新建 major contract。
- 读取方必须忽略未知字段、容忍缺失 optional 字段；不得解析 Markdown 或将内部 diagnostics 当作产品字段。
- 旧详情 artifact 没有 `profile` 时应继续以既有研究详情渲染，不能报错。

## Profile Artifact

`outputs/fund_profiles/fund_profile-<code>.json` 的必填顶层字段：

| 字段 | 含义 |
| --- | --- |
| `schema_version` | 固定为 `1.0`。 |
| `generated_at` | ISO 8601 UTC 生成时间。 |
| `generator` | 生成器，例如 `ya-fundmind/3.0.0a1`。 |
| `code` | 规范化六位基金代码。 |
| `as_of` | 本次资料快照日期，可为 `null`。 |
| `profile` | `FundProfile` 对象或 `null`。 |
| `trading_rule` | `FundTradingRule` 对象或 `null`。 |
| `fees` | `FundFee` 数组，可为空。 |
| `data_status` | `updated`、`attention`、`limited` 或 `unavailable` 的结构化状态。 |
| `not_production_model` | 固定 `true`。 |
| `main_score_changed` | 固定 `false`。 |
| `main_risk_changed` | 固定 `false`。 |

`profile` 可用字段：`code`、`name`、`full_name`、`fund_type`、`fund_company`、`custodian`、`fund_manager`、`issue_date`、`inception_date`、`asset_scale`、`asset_scale_unit`、`share_scale`、`share_scale_unit`、`benchmark`、`tracking_target`、`source`、`as_of`、`updated_at`、`expires_at`、`stale`、`metadata`。

`trading_rule` 可用字段：`code`、`purchase_status`、`redemption_status`、`purchase_start_date`、`redemption_start_date`、`source`、`as_of`、`updated_at`、`expires_at`、`stale`、`metadata`。

每个 `FundFee` 必须有 `code`、`fee_type`、`condition`、`period`、`original_rate`、`discounted_rate`、`source`、`as_of`、`updated_at`、`expires_at`、`stale`；展示费率字段均是 `string | null`，以避免把“每笔 1000 元”等金额条件错误转成百分比。

## 数据与新鲜度

- `source` 使用 `akshare` 或 `cache:akshare`；fallback 不能覆盖原始来源语义。
- `as_of` 表示数据所适用日期，`updated_at/expires_at` 表示本地采集与 TTL；`stale=true` 表示过期 cache。
- endpoint 不可用、单字段缺失、全量快照未预热必须产出可理解状态和 diagnostics warning；不得构造值。
- 产品 API 不返回 `source`、`stale`、`metadata`、endpoint 名称或 raw warning code；这些仅属于 artifact、trace 和系统诊断。

## Product API

`GET /api/product/funds/{code}/profile` 返回用户字段：

```json
{
  "fund": {"code": "021511", "name": "示例基金", "fund_type": "混合型"},
  "profile": {"fund_company": "示例公司", "inception_date": "2024-01-01"},
  "trading_rule": {"purchase_status": "可申购", "redemption_status": "可赎回"},
  "fees": [{"fee_type": "申购费率", "condition": "小于100万元", "original_rate": "1.20%", "discounted_rate": "0.12%"}],
  "data_status": {"state": "updated", "label": "资料已更新", "description": "资料可供浏览", "as_of": "2026-07-28"}
}
```

`GET /api/funds/{code}/profile` 可以提供 diagnostics 给本地系统工具；该接口仍必须固定 output root，不接收任意路径或 URL。

## Trace 与错误分类

每次显式 profile/参考快照刷新写 Provider Trace v1。endpoint 名称为 `fund_name_em`、`fund_open_fund_rank_em`、`fund_etf_spot_em`、`fund_purchase_em`、`fund_overview_em`、`fund_fee_em`。每个 endpoint 保存 attempts、success、error、raw/mapped/skipped/cache-write count；可分类 `config_missing`、`timeout`、`connection_error`、`http_error`、`invalid_response`、`empty_response`、`mapping_error`。

## 下游读取建议

- Web 仅读取 Product API；CLI/Skill/MCP 可读取 artifact 和受限 diagnostics API。
- 资料层不应写入 `FundRecord`、主 score 或主 `risk_issues`。
- 缺少 profile 不代表该基金不存在，也不代表产品质量差；它只能产生资料状态和缺口提示。
