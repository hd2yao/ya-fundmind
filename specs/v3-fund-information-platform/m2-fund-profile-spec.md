# V3 M2 Fund Profile Data Spec

## 背景和目标

V3 M1 已把市场、基金、自选和组合整理为用户可浏览的产品骨架，但基金详情仍主要来自现有研究产物。M2 在不改变研究模型的前提下，把 AKShare 已公开的基金概况、申购赎回状态和费率接入为独立资料层，使已索引基金可以展示真实、可追溯的产品资料。

## 用户场景

- 用户从“基金终端”搜索已索引基金，打开稳定 URL，查看基金类型、管理人、托管人、成立日、规模、业绩基准和跟踪标的。
- 用户查看申购/赎回是否可用及主要费率条件；缺失或尚未同步时看到自然语言状态，不看到 endpoint、缓存或 raw warning。
- 用户切换“概览 / 净值与业绩 / 费率与规则”标签；历史净值继续复用既有 M1 路径。
- 系统维护者可显式预热全量目录或申购状态，不会因用户点击详情页而触发全量 AKShare 请求。

## 范围

- 标准化 AKShare `fund_name_em`、`fund_open_fund_rank_em`、`fund_etf_spot_em` 的基金目录并集，并记录 endpoint coverage。
- 标准化单基金 `fund_overview_em` 与 `fund_fee_em`；将 `fund_purchase_em` 写成全量 TTL 快照后供详情读取。
- 新增 `FundProfile`、`FundTradingRule`、`FundFee` 及 bundle/service、SQLite cache、Provider Health/Trace、CLI、JSON artifact、产品 API 和详情标签页。
- 为新 profile artifact 增加 v1 contract validation；产品 API 继续隔离 source、cache、warning code 和原始异常。

## 非目标

- 不接持仓、评级详情、经理大全、分红、拆分或同类推荐。
- 不修改 `FundRecord`、主评分、主风险、daily 默认 Provider、`configs/watchlist.yaml`、`configs/portfolio.yaml` 或 scheduler。
- 不把 Tiantian 设为默认或替代 AKShare；不输出买卖建议、收益承诺、交易指令或券商能力。
- 不把全量 `fund_purchase_em` 请求放进详情页或每只基金的按需服务。

## 验收标准

- `AC-M2-01`：已索引六位基金代码可读取 profile；概况返回 full name、类型、公司、托管、经理、成立日、资产/份额规模、基准和跟踪标的中的可用字段。
- `AC-M2-02`：申购/赎回与费率单独建模；费用条件、期限、原费率、优惠费率均保留为原始展示文本，不将固定金额错误解析为百分比。
- `AC-M2-03`：目录和申购状态仅由显式预热命令写入 TTL snapshot；详情只按 code 调用 `fund_overview_em` / `fund_fee_em`，并优先读 fresh cache。
- `AC-M2-04`：live 失败时仅在同类 cache 存在时 fallback；stale/partial/missing 均可表达，且字段级 `source/as_of/updated_at/expires_at/stale` 在 diagnostics 可追踪。
- `AC-M2-05`：产品 API `/api/product/funds/{code}/profile` 和详情页展示中文状态，不泄露 provider、cache、schema、raw warning 或绝对路径。
- `AC-M2-06`：默认 pytest/CI 不访问网络；mapping、坏行、migration、fresh/stale fallback、trace、API、Web 和 contract 均有测试。
- `AC-M2-07`：alpha.2 前用 3 种代表性基金（开放式混合、ETF 联接、场内 ETF）完成真实 smoke，保留 trace；任一核心 endpoint 不可用或 mapping 无法验证则不发布 alpha.2。

## 约束和假设

- 当前 AKShare 版本为 `1.18.64`；官方文档将 `fund_overview_em` 定义为单基金基本概况、`fund_fee_em` 定义为单基金费率、`fund_purchase_em` 定义为全量申购状态。实现必须以 runtime 返回形状为准，真实 smoke 只验证而不伪造结果。
- `fund_fee_em` 的 indicator 与列名可能随数据源变化；映射使用已知别名并将未知列保留在 diagnostics metadata，不向产品响应暴露。
- 缺失、非数值规模或“该基金无跟踪标的”均是数据状态，不得转成零值、正向信号或推荐结论。

## 待确认问题

无阻断问题。实际 fee indicator 的可用组合、三类 smoke 代码和字段列名以实现阶段的真实 endpoint 结果写入 trace/验收报告；若与本 spec 的字段语义冲突，先更新本 spec、contract 和计划后再继续。
