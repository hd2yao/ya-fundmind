# Product API v1

## 用途

`/api/product/*` 是 Product Web 的只读用户层接口。它从既有结构化产物与服务中构建面向基金信息平台的 view model；不替代研究 JSON、provider trace 或诊断接口。

市场、基金、自选和组合等信息浏览页只能读取本契约中的字段。`/api/*` 既有端点继续保留，供 v2.6 兼容、测试和系统诊断使用；页面不得把其中的 provider、cache、schema、expires、raw warning code 或绝对路径直接渲染出来。系统状态、人工审核和报告中心属于二级工具页，也必须使用中文业务文案，而不是直接渲染内部字段。

## 响应形式

从结构化产物读取集合的端点（当前为 `/api/product/market`、`/api/product/watchlist`、`/api/product/portfolio`）返回资源包络：

```json
{
  "availability": "available",
  "generated_at": "2026-07-28T12:00:00+00:00",
  "data": {}
}
```

- `availability`：`available` 或 `missing`。
- `generated_at`：本地结构化产物最后更新时间；缺失时为 `null`。
- `data`：对应产品 view model；字段缺失用 `null` 或空集合表达，不用 `0` 伪造事实。

搜索、详情和历史端点直接返回对应的产品 view model；它们同样包含 `availability`（适用时）、`data_status` 与文档列出的核心字段，但不额外嵌套 `data`。前端不得依赖响应外的内部字段，也不得通过 Markdown 推断数据状态。

## 数据状态

所有可展示数据都使用下列用户层状态，不输出内部 `normal`、`warning`、`degraded`、`stale`、`fallback` 或 warning code：

```json
{
  "state": "updated",
  "label": "数据已更新",
  "description": "当前展示截至 2026-07-27 的结构化数据。",
  "as_of": "2026-07-27"
}
```

`state` 只用于产品视觉语义：`updated`、`attention`、`limited`、`unavailable`。下游必须显示 `label` 和 `as_of`，而非反向解释内部质量字段。

## 端点

| 端点 | 用途 | 核心数据 |
| --- | --- | --- |
| `GET /api/product/market` | 行情页摘要 | 市场日期、覆盖范围、主题、数据状态 |
| `GET /api/product/market/indices/{symbol}/history` | 指数历史 | 指数点位、窗口、数据日期、数据状态 |
| `GET /api/product/market/sectors` | 行业板块目录 | 板块摘要、服务端分页、数据日期、数据状态 |
| `GET /api/product/market/sectors/{symbol}/history` | 板块历史 | 板块点位、窗口、数据日期、数据状态 |
| `GET /api/product/funds/search` | 基金库服务端分页 | 基金摘要、筛选 facets、数据日期、数据状态 |
| `GET /api/product/funds/{code}` | 基金资料 | 基金摘要、补充资料、字段缺口说明 |
| `GET /api/product/funds/{code}/history` | 基金净值曲线 | 净值点、窗口、数据日期、数据状态 |
| `GET /api/product/watchlist` | 只读自选页 | 配置自选基金、覆盖摘要、数据状态 |
| `GET /api/product/portfolio` | 组合页 | 配置持仓、估值状态、暴露、观察项 |

产品基金摘要只包含：代码、名称、类型、主题、净值、规模、场内标记、收益窗口、数据日期和数据状态。它不包含 `source`、`updated_at`、`expires_at`、`stale`、`fallback_reason` 或原始质量等级。

组合估值状态使用中文业务语义：`估值已齐全`、`部分持仓待估值`、`当前估值暂不可用`、`尚未配置持仓`。缺失估值保持 `null`，不生成零值、`-100%` 或权重。

当指数或板块历史暂不可用时，产品端点以 `availability: "missing"`、空 `points/items` 和中文 `data_status` 正常响应；历史空态固定使用 `label: "历史日线暂未取得"`，并以资源相关的自然语言说明下一步可查看的内容。普通页面不透传底层请求失败、来源、缓存或 provider 信息。

## 兼容性

- 这是新增接口，不删除或重命名 v2.6 机器可读输出与既有 `/api/*` 路由。
- 新字段仅以 optional 方式增加；普通 Product Web 不解析 Markdown。
- 详细 provider/cache/trace 信息仅由后续系统诊断视图读取。
