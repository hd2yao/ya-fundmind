# 基金信息平台开源项目复盘

调研日期：2026-07-28

## 调研目标

本轮不是再次泛泛搜索金融 Agent，而是回答三个具体问题：

1. 一个面向普通用户的基金信息平台还应展示哪些模块？
2. AKShare 已提供哪些可复用数据能力？
3. 哪些参考项目只适合学习架构，不能照搬代码或交易结论？

初始调研保留在 `docs/archive/research/`。该目录记录的是 2026-06-22 的 MVP 状态，其中 cache、Tiantian、Web、Skill/MCP 等多项缺口已经完成，不再作为当前路线依据。

## 深度参考项目

### 1. AKShare

定位：财经数据接口库，也是当前系统的主要 live provider。

可学习和可直接适配的数据模块：

- 全市场基金基础目录：`fund_name_em`
- 单基金基本信息：`fund_info_ths`、`fund_individual_basic_info_xq`
- 基金概况：`fund_overview_em`
- 申购/赎回状态：`fund_purchase_em`
- 费率和交易规则：`fund_fee_em`、`fund_individual_detail_info_xq`
- ETF 快照和历史：`fund_etf_spot_em`、`fund_etf_hist_em`
- 基金持仓和资产配置：`fund_portfolio_hold_em`、`fund_portfolio_bond_hold_em`、`fund_individual_detail_hold_xq`
- 基金评级：`fund_rating_all`
- 基金经理：`fund_manager_em`
- 风险收益分析：`fund_individual_analysis_xq`
- 指数快照和历史：`stock_zh_index_spot_em` 及现有日线接口

采用原则：

- AKShare 是接口聚合库，字段和上游网页可能变化；必须经过 provider、标准模型、cache、trace 和质量门。
- 不把 AKShare DataFrame 原始列直接返回前端。
- 每个 endpoint 独立记录 source、as_of、updated_at、stale 和错误。
- 缺失字段保留 `null`，不得转换成有业务含义的 0。

### 2. ZhuLinsen/daily_stock_analysis

定位：多数据源、自动运行、Web/API、历史报告和研究工作流较完整的股票分析系统。

可借鉴：

- 数据 provider 与业务分析分层。
- Web 服务与定时分析进程可以独立运行。
- 历史报告、任务状态、数据块来源和 fallback 可回看。
- 配置、Docker、定时任务和本地 Web 的开源交付体验。

不采用：

- 股票买卖计划、止盈止损和模拟交易输出。
- LLM 作为基金资料平台的核心依赖。
- 在普通基金页面展示完整运行诊断。

### 3. Deng-XueCheng/fund-investment-assistant

定位：A 股公募基金研究系统，包含全市场基金、组合、费用、风险和多 Agent。

可借鉴：

- 基金资料、基金经理、费用、持仓和组合分析是独立模块。
- provider 需要 retry、cache、circuit breaker 和审计。
- 组合页需要相关性、集中度和风险暴露，而不是只列持仓。
- 所有实验信号和主结论分离。

不采用：

- 直接照搬 smart score、买入建议或 Agent 投票。
- 在基金资料未完整前优先做复杂模型。

### 4. oujingzhou/OpenFR

定位：覆盖股票、基金、指数、期货和宏观的金融研究 Agent。

可借鉴：

- 市场、基金、宏观和新闻工具分域。
- fallback、cache、中间产物和节点可观测。
- 前端只消费结构化服务，不解析报告文本。

不采用：

- 将 LangGraph、多 Agent 辩论放入 V3 核心。
- 以最终买卖结论作为平台目标。

### 5. muxuuu/serenity-skill

定位：强调来源质量、证据链、失败条件和下一步核验的研究 Skill。

可借鉴：

- 来源分级和证据强度。
- 结论必须关联可定位证据。
- 数据不足时显示下一步核验，而不是补造答案。

不采用：

- 把 Skill 模板直接当成基金详情页面。
- 在核心基金浏览链路里要求 LLM。

## 补充参考

| 项目 | 可学习点 | 本轮采用程度 |
| --- | --- | --- |
| `ai-hedge-fund` | 信号、风险和组合决策分离 | 仅保留边界思想 |
| `A_Share_investment_Agent` | Agent 状态与中间报告 | 仅学习；许可和非商业条款需单独审查，不复制代码 |
| `WealthAgent` | ETF、联接、QDII、主动基金的差异化展示/估值 | 采用基金类型分层思想 |
| `Awesome Finance Skills` | 能力按 Skill 独立组织 | 已有 V2 Skill/MCP，不作为 V3 主线 |
| `stock-analytics-skill` | 本地配置和场景路由 | 自选/持仓配置继续本地化 |

补充参考只作概念研究，本轮没有固定其 commit，也没有把代码或 license 带入 V3。任何后续代码采用必须重新核对当时的 LICENSE、NOTICE 和数据源条款。

| 项目 | 仓库 | 访问日期 | 许可处理 |
| --- | --- | --- | --- |
| `ai-hedge-fund` | <https://github.com/virattt/ai-hedge-fund> | 2026-07-28 | study-only，采用前重审 |
| `A_Share_investment_Agent` | <https://github.com/24mlight/A_Share_investment_Agent> | 2026-07-28 | 存在额外使用边界，仅研究，不复制 |
| `WealthAgent` | <https://github.com/hkwuks/WealthAgent> | 2026-07-28 | study-only，采用前重审 |
| `Awesome Finance Skills` | <https://github.com/RKiding/Awesome-finance-skills> | 2026-07-28 | study-only，采用前重审 |
| `stock-analytics-skill` | <https://github.com/belos-street/stock-analytics-skill> | 2026-07-28 | study-only，采用前重审 |

## 模块清单

### 基金平台核心模块

1. **市场总览**
   主要指数快照与历史、涨跌分布、行业板块榜单和走势。
2. **全市场基金目录**
   代码、名称、类型、最新净值/价格、日期、收益窗口、规模、费率、可申购状态。
3. **自选基金**
   与全市场明确区分，展示关注原因、最新变化和数据日期。
4. **基金概览**
   基金全称、类型、成立日期、规模、公司、经理、托管人、基准、跟踪标的。
5. **净值与业绩**
   单位/累计净值、历史曲线、区间收益、回撤、波动和同类位置。
6. **ETF 行情**
   最新价、涨跌、成交量/额、OHLC、IOPV、折溢价、换手率；只对场内基金显示。
7. **费率与交易规则**
   申购/赎回状态、起购金额、确认日、管理费、托管费、销售服务费、分档费率。
8. **持仓与资产配置**
   股票/债券持仓、资产类别比例、报告期和数据滞后说明。
9. **经理与公司**
   经理任职、在管基金、从业时间、规模；公司信息。
10. **评级与同类比较**
    评级机构、星级、同类排名、风险收益指标。
11. **分红/拆分**
    历史分红和拆分事件。
12. **组合**
    本地只读持仓、成本、可用估值、暴露和缺口；未知值不得显示为真实亏损。
13. **研究证据**
    真实来源接入后再展示新闻/公告；当前 fixture 仅用于测试。
14. **数据状态**
    provider、缓存、stale、fallback、trace 和 contract，放在系统/诊断区。

## 参考项目映射

| 参考项目 | 可借鉴设计 | 当前项目模块 | 当前状态 | 采用决定 | 后续任务 |
| --- | --- | --- | --- | --- | --- |
| AKShare | 基金概况、费用、持仓、评级、经理 | `providers.py`、`models.py`、`cache.py` | 目录/净值已接，档案未完整 | 深度采用接口能力，不暴露原始列 | V3 M2/M4 |
| AKShare | ETF 快照和历史 | `FundRecord`、fund history、Web | 只映射少量 spot 字段 | 新建 ETF Quote 视图模型 | V3 M3 |
| AKShare | 指数快照与历史 | market history | 历史已接，快照有限 | 扩展市场摘要 | V3 M3 |
| daily_stock_analysis | Web/API 与 scheduler 分离 | Product Web、daily/weekly | 已吸收 | 保持独立进程和本地优先 | V3 M6 |
| daily_stock_analysis | 历史浏览和配置管理 | Reports、watchlist | 部分实现 | 自选先只读产品化，写配置后置 | V3 M5 |
| fund-investment-assistant | 基金资料分域 | Fund Detail | 部分实现 | 采用模块划分，不采用评分公式 | V3 M2/M4 |
| fund-investment-assistant | 组合数据真实性和风险暴露 | Portfolio | 部分实现且有误导性 0 | 先修 unknown 语义，再做组合体验 | V3 M1/M5 |
| OpenFR | 结构化工具和中间产物 | Artifact/Query/Evidence | 已实现 | 继续复用，不扩 Agent 主线 | 保持 |
| serenity-skill | 来源与证据分级 | Evidence/Copilot | 已实现基础 | 新闻真实来源后复用 | V3 之后 |
| WealthAgent | 按基金类型展示 | Valuation/Fund Detail | 部分实现 | ETF、联接、QDII、开放式基金使用不同模板 | V3 M2/M3 |

## 数据来源边界

### AKShare 能解决

- 基金目录、净值、部分基金档案、费率、持仓、评级、经理。
- ETF 行情快照和历史。
- 指数、行业板块和部分市场统计。

### AKShare 不能等同解决

- 交易所授权级实时行情和毫秒级推送。
- 券商订单、账户、实际成交和资金操作。
- 稳定、完整、可再分发的新闻/公告许可。
- 对所有上游字段的永久稳定保证。

### 新闻/公告

新闻和公告需要独立 provider、许可和来源质量策略，不能把 fixture 或搜索结果当正式数据。V3 核心基金资料平台不以新闻接入作为首个 blocker，但正式产品必须隐藏演示数据。

## 开源采用规则

- 只学习架构、数据分层、模块边界和交付方法。
- 不复制参考项目的交易逻辑、提示词、评分公式或受限许可代码。
- 引入第三方代码前单独核对 license、NOTICE、数据源条款和再分发限制。
- README 必须说明 AKShare 是第三方接口库，上游数据可能变化；本项目不保证实时性或适合作为交易依据。

## 一手来源

- [AKShare 公募基金数据](https://akshare.akfamily.xyz/data/fund/fund_public.html)
- [AKShare 指数数据](https://akshare.akfamily.xyz/data/index/index.html)
- [akfamily/akshare](https://github.com/akfamily/akshare)
- [ZhuLinsen/daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis)
- [Deng-XueCheng/fund-investment-assistant](https://github.com/Deng-XueCheng/fund-investment-assistant)
- [oujingzhou/openfr](https://github.com/oujingzhou/openfr)
- [muxuuu/serenity-skill](https://github.com/muxuuu/serenity-skill)
