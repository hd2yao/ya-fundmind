# V3 M1 产品 View Model 与诊断隔离

## 目标

完成 V3 M1 的 `T101`、`T102` 与 `T105`：普通 Product Web 改读用户层 view model，未知字段保持 `null`，诊断信息留在兼容/系统路径。此批不新增 AKShare endpoint，不修改主评分、主风险、daily 默认 provider、watchlist、portfolio 或 scheduler。

## 实施顺序

1. 为状态转换、optional 字段和诊断隔离写 Python 失败测试。
2. 实现无副作用的 `product_views` mapper；输入为既有 JSON/service 响应，输出只含用户层字段。
3. 在 `web_api` 新增 `/api/product/*`（包括指数/板块的目录与历史子资源），不破坏 v2.6 `/api/*`。
4. Web 的市场、基金、自选、基金详情/历史和组合页迁移到 Product API，所有状态显示中文业务文案。
5. 完成 Python/React、1440/768/375、console 和基础 accessibility 验收。

## P1 产品语言收口（2026-07-28）

在产品 view model 完成后，额外处理真实产物与浏览器验收发现的问题：

1. 旧组合产物没有 `valuation_status` 时，禁止将 `0`、`-100%` 或零权重作为真实估值输出；有持仓时统一显示“当前估值暂不可用”。
2. 基金详情中的 `unknown`、`--`、`N/A`、`null` 等上游占位必须映射为 `null`，由页面显示自然语言缺失状态。
3. 普通导航隐藏没有正式、可核验资料的新闻入口；直接访问时仅显示“研究证据暂未开放”。
4. 系统、报告、研究助手和人工审核页面保留功能，但必须将运行状态、审核状态和证据状态翻译为中文业务文案，隐藏 artifact path、原始状态码、来源名和内部标识。

这些变更只改 Product Web projection，不改原始 JSON、cache、评分、风险、用户配置或 scheduler。

## 验收

- 缺失收益、净值、规模、估值仍为 `null`/`--`，不被转换成正向或零值。
- Product API 与普通页面不包含 provider、cache、schema、expires、raw warning code、绝对路径或英文内部质量码。
- 指数或板块数据暂不可用时，Product API 返回中文空状态而非技术性 `503` 文案；旧诊断端点行为保持不变。
- `updated`、`attention`、`limited`、`unavailable` 都有中文 label、说明和数据日期。
- 现有 `/api/funds/search`、`/api/funds/{code}`、`/api/market`、`/api/portfolio` 和相关测试保持兼容。
- 主评分、主风险、daily/weekly 与用户配置不变。
- 真实旧组合产物在 Product API 中不再出现 `0`、`-100%` 或零权重伪估值；浏览器组合页显示“暂不可计算”和 `--`。
- 直接访问 `/news`、`/status`、`/reports`、`/copilot`、`/review` 不显示 provider/cache/path/raw code 或英文质量状态。

## 回滚

新增端点与前端调用可通过本 PR 的单个 merge commit 回滚；旧 API、SQLite schema、缓存和输出文件不被迁移或删除。
