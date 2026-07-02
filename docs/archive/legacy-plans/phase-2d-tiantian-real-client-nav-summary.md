# Phase 2D Tiantian Real Client Hardening + NAV Summary

## Phase 2D 目标

Phase 2D 在 Phase 2C 的最小 TiantianFundProvider 之上，强化真实 client 的可运行性和可观测性，并增加历史净值统计摘要。

本阶段只做：

- Tiantian 兼容服务 client 配置、timeout、retry 和分页
- 基金详情字段质量 warning
- 历史净值坏行隔离和 trace 记录
- `fund_details`、`nav_history_summary` JSON 可选输出
- cache 写入和 contract validation 兼容

本阶段不做：

- 不把 Tiantian 数据接入评分模型
- 不把 Tiantian 数据接入风险主逻辑
- 不改变 daily 默认 provider
- 不做真实交易
- 不承诺收益
- 不引入 Web、MCP、LLM、LangGraph

## Tiantian Real Client 配置方式

真实 Tiantian smoke 需要通过环境变量显式配置兼容服务地址：

```bash
export TIANTIAN_API_BASE_URL=http://127.0.0.1:3000
python -m fund_agent.cli smoke-tiantian --code 510300 --output-dir outputs
```

如果未设置 `TIANTIAN_API_BASE_URL`，`smoke-tiantian` 会返回清晰错误，并且不会伪造成功：

```bash
python -m fund_agent.cli smoke-tiantian --code 510300 --output-dir outputs
```

Tiantian runtime 配置位于 `configs/providers.yaml`：

```yaml
tiantian:
  timeout_seconds: 20
  retry_count: 0
  retry_backoff_seconds: 0
  trace_retention_days: 30
  max_trace_files: 100
```

环境变量也可覆盖真实 client：

- `TIANTIAN_TIMEOUT_SECONDS`
- `TIANTIAN_RETRY_COUNT`
- `TIANTIAN_RETRY_BACKOFF_SECONDS`

## 分页策略

`fetch_nav_history(code, start_date=None, end_date=None)` 使用兼容服务的 `fundMNHisNetList` endpoint，并从第一页开始分页拉取：

- `pageIndex` 从 `1` 开始
- `pagesize` 默认 `200`
- 如果响应包含 `TotalPages`、`totalPages`、`pages` 或 `total_pages`，按总页数停止
- 如果没有总页数，遇到返回行数小于 `pagesize` 时停止
- 每页调用都会进入 provider trace 的 `endpoints`
- `start_date`、`end_date` 在返回行上做本地过滤

坏行只会增加 `skipped_row_count` 和 `skipped_rows` warning，不影响其他净值点写入 cache。

## 错误分类

Tiantian client 将错误归类为稳定 code，写入 provider warning 和 trace：

- `config_missing`: 配置缺失；当前表现为 provider unavailable，不发起网络请求
- `connection_error`: DNS、连接失败或底层 URL 错误
- `timeout`: 请求超时
- `http_error`: HTTP 非成功响应
- `invalid_response`: JSON 解析失败或响应根节点类型不符合预期
- `empty_response`: 详情或净值 endpoint 返回空数据
- `mapping_error`: provider 映射阶段出现未预期异常

这些 warning 用于数据质量观察，不进入评分和风险主逻辑。

## 基金详情数据质量

`fetch_fund_detail` 成功返回后会检查以下字段：

- `name`
- `fund_company`
- `fund_manager`
- `scale`
- `rating`
- `inception_date`

缺失字段会生成 `detail_missing_*` warning，但不会中断 enrichment，也不会影响 daily 主流程。

## nav_history_summary 字段说明

`fund_agent_report.json` 中的 `nav_history_summary` 是可选字段，按基金 code 输出：

```json
{
  "510300": {
    "count": 3,
    "start_date": "2026-06-20",
    "end_date": "2026-06-22",
    "latest_unit_nav": 1.05,
    "latest_accumulated_nav": 1.05,
    "total_return": 5.0,
    "annualized_return": 752645.6421,
    "max_drawdown": -4.5455,
    "volatility": 7.2727,
    "missing_days": 0,
    "source": "tiantian",
    "data_quality_grade": "normal"
  }
}
```

字段含义：

- `count`: 有效历史净值点数量
- `start_date` / `end_date`: 样本日期范围
- `latest_unit_nav`: 最新单位净值
- `latest_accumulated_nav`: 最新累计净值
- `total_return`: 样本区间总收益率，百分比
- `annualized_return`: 样本区间年化收益率，百分比；短样本会非常不稳定，仅供观察
- `max_drawdown`: 样本区间最大回撤，百分比
- `volatility`: 样本内日收益波动率，百分比
- `missing_days`: 日期范围内未观察到的自然日数量
- `source`: 数据来源
- `data_quality_grade`: `normal`、`warning` 或 `degraded`

这些指标仅作为观察摘要，不进入评分和风险模型。

## Cache 写入说明

Tiantian enrichment 成功后写入现有 SQLite cache：

- `fund_details`: 基金详情
- `fund_navs`: 历史净值点

读取 cache 时继续保留：

- `source`
- `as_of`
- `updated_at`
- `expires_at`
- `stale`

Tiantian cache source 使用 `cache:tiantian`。

## Provider Trace

Tiantian trace 继续遵守 `docs/contracts/provider-trace-v1.md`，示例：

```json
{
  "provider": "tiantian",
  "provider_version": null,
  "live_row_count": 4,
  "mapped_row_count": 3,
  "skipped_row_count": 1,
  "cache_write_count": 4,
  "fallback_used": false,
  "endpoints": [
    {
      "endpoint": "tiantian_fund_detail",
      "attempts": 1,
      "success": true,
      "timeout_seconds": 20
    },
    {
      "endpoint": "tiantian_nav_history",
      "attempts": 1,
      "success": true,
      "timeout_seconds": 20,
      "live_row_count": 200
    }
  ],
  "warnings": [
    {
      "code": "skipped_rows",
      "severity": "warning"
    }
  ]
}
```

Trace 不包含密钥或敏感信息，trace retention 继续按 provider 配置清理旧 trace。

## 为什么仍不接入评分和风险

Tiantian 的详情、评级、规模和历史净值摘要对后续研究有价值，但 Phase 2D 的目标是先稳定数据接入、cache、trace 和输出契约。直接接入评分或风险会扩大行为变化面，影响 AKShare/fixture 回归和报告解释性。

因此本阶段只输出可选字段：

- `fund_details`
- `nav_history_summary`

后续进入评分/风险前，需要先定义指标语义、样本窗口、缺失数据策略和回归测试。

## 验证命令

```bash
python -m pytest -q
python -m compileall -q fund_agent
python -m fund_agent.cli demo --output-dir outputs --as-of 2026-06-23
python -m fund_agent.cli daily --provider fixture --watchlist-file configs/watchlist.yaml --portfolio-config configs/portfolio.yaml --output-dir outputs --as-of 2026-06-23
python -m fund_agent.cli validate-contract --output-dir outputs
```

如果已设置真实兼容服务：

```bash
python -m fund_agent.cli smoke-tiantian --code 510300 --output-dir outputs
```

## Phase 2E 建议

- 在有稳定 Tiantian 兼容服务后增加手动 smoke CI job。
- 为 NAV summary 增加更稳定的窗口参数，例如近 1 月、3 月、6 月。
- 增加 Tiantian cache fallback 读取路径，但仍保持 explicit enrichment，不接 daily 默认流程。
- 设计基金详情字段进入评分/风险前的数据契约和回归评估。
