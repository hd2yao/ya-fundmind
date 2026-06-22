# Open Source Study

调研日期：2026-06-22

本文只归纳可复用的架构、数据源、模块划分、报告方式、Agent 分工和 Skill 组织方式；不建议直接搬运参考项目代码。

## 总体判断

当前 `fund_agent` MVP 更接近“基金投研 + 持仓管理 + 风控日报 + 可被 Agent 调用的本地 CLI”，而不是完整的“自动投资大师 Agent”。它已经吸收了多个项目的设计方向，但实现方式是自行写的轻量 Python 包：数据结构、评分函数、估值分类、组合分析、报告渲染和 CLI 都是本仓库内独立实现，没有直接复制参考项目的工程结构或代码。

当前已吸收的设计主要包括：

- `daily_stock_analysis` 的每日分析报告、Markdown/HTML 输出、数据源降级和后续推送方向。
- `fund-investment-assistant` 的基金优先、反追高评分、持仓分析和风险提示方向。
- `WealthAgent` 的基金估值类型分层，尤其是 ETF/LOF、ETF 联接、QDII、指数/NAV-only 的差异化处理。
- `A_Share_investment_Agent`、`ai-hedge-fund`、`OpenFR` 的“分析 -> 辩论/风险 -> 组合经理 -> 报告”多角色思路，但当前只实现为确定性类和运行摘要。
- `serenity-skill`、`Awesome Finance Skills`、`stock-analytics-skill` 的 Skill 化、证据分级、风险边界和“CLI + Agent 配置”方向，但当前没有真正的 Skill 包。

## 参考项目学习点

| 参考项目 | 定位 | 可学习点 | 对 fund_agent 的启发 | 当前吸收程度 |
| --- | --- | --- | --- | --- |
| `ZhuLinsen/daily_stock_analysis` | 多市场股票日常分析系统，覆盖行情、新闻、公告、基本面、Web 工作台和自动推送。 | 每日固定流程、多源数据聚合、工作台/历史报告、推送渠道、可降级的数据边界、风险和检查清单式报告。 | fund_agent 可以把“日报”作为第一交付物，先稳定本地 CLI，再扩展定时任务、通知和 Web 工作台。 | 部分吸收：已有 Markdown/HTML 日报、风险提示和 CLI；未实现 Web 工作台、推送、新闻公告、多源市场数据。 |
| `muxuuu/serenity-skill` | 面向 Agent 的投研 Skill，强调从叙事到产业链卡点、证据链、失败条件和下一步核验。 | 先排层级再排标的、证据强弱标签、失败条件、下一步核验、研究支持边界、Skill 包结构和本地 scorecard。 | fund_agent 的基金研究也应输出“为什么优先研究、证据强度、什么情况说明判断错、下一步查什么”。 | 概念吸收：已有 `evidence_label`、风险免责声明和下一步核对；未实现 Skill 包、证据来源分级、来源路径和失败条件模板。 |
| `akfamily/akshare` | Python 财经数据接口库，覆盖股票、基金、指数、期货、外汇等，强调数据采集、清洗、落地和文档。 | 把数据供应商隔离在 provider 边界；接口字段会变化，需要缓存、降级、字段映射和版本维护。 | fund_agent 不应把 AKShare 直接散落在业务逻辑里，应保持 provider abstraction，并为基金接口建立字段契约。 | 部分吸收：已有 `AkshareProvider` 和 `FixtureProvider`；未实现缓存、字段契约文档、接口变更检测和多接口补充。 |
| `kouchao/TiantianFundApi` | 天天基金 Node.js API 服务，强调字段可读性、持续更新、测试和 Docker/Vercel 部署。 | 天天基金适合作为基金净值、排行、经理、评级、基金公司、历史净值的补充数据源；但接口命名和结构需要统一。 | fund_agent 下一步应建立 `TiantianFundProvider` 或数据适配层，重点统一字段而不是暴露原始结构。 | 未实现：当前没有天天基金 provider，也没有基金经理、评级、历史净值、基金公司等字段。 |
| `24mlight/A_Share_investment_Agent` | A 股投资多 Agent 概念验证，基于多角色分析、LLM、辩论室和后端状态 API。 | 角色分工、LLM 评审、情绪分析、Agent 状态 API、运行状态可视化、从 `ai-hedge-fund` 适配到 A 股。 | fund_agent 可以先保留确定性核心，再增加可选 LLM 评审和状态追踪，而不是让 LLM 直接控制结果。 | 概念相似：已有 agent-style 类和 trace；未实现 LLM、辩论室、状态 API、情绪新闻、后端服务。 |
| `ai-hedge-fund` | AI hedge fund 概念验证，多个投资风格 Agent、估值/情绪/基本面/技术 Agent、风控和组合经理。 | 把“信号生产”和“组合决策”分开；Risk Manager 设仓位限制；Portfolio Manager 汇总各类信号但不真实交易。 | fund_agent 应区分候选评分、估值、组合风险和最终建议，不应把评分直接等同买卖动作。 | 部分吸收：已有 Screening/Valuation/Risk/Portfolio/Report 角色名；未实现多策略投票、仓位限制、订单模拟、风格 Agent。 |
| `OpenFR` | 轻量金融研究 Agent，AKShare + 多 LLM + LangGraph；覆盖股票、基金、期货、指数、宏观。 | 三阶段流程：数据与分析、牛熊辩论、三方风险评估；完整中间报告、节点耗时、fallback sources、cache friendly。 | fund_agent 可以把确定性 MVP 升级为可观察工作流：每个节点产物可保存、可复查、可限时。 | 概念相似：已有线性 agent trace；未实现 LangGraph、辩论、多轮风险评估、中间报告、节点耗时和 fallback source。 |
| `fund-investment-assistant` | A 股公募基金投研系统，6 Agent、smart_score、持仓建议、组合风险、费用感知和审计追踪。 | 最贴近本项目：反追高评分、基金持仓文件、组合风险、费用/短赎、市场状态自适应、审计投票、配置驱动。 | fund_agent 应优先补齐费用、相关性/CVaR、市场状态、审计追踪和配置化阈值。 | 部分吸收：已有反追高评分、持仓市值、权重偏离、集中度和日报；未实现 6 Agent、费用、相关性、CVaR、动态权重、审计投票。 |
| `WealthAgent` | 基金估值和智能理财 Agent 框架，含前后端、实时估值、批量估值、基金详情、历史净值和策略类型。 | 估值方法分层：实时价格、指数估值、持仓估值、债券/股票混合、QDII 混合、benchmark-only；接口可返回估值详情和准确性。 | fund_agent 的估值模块应该从“分类 + 最新净值”升级为“方法选择 + 计算公式 + 数据缺口 + 置信度 + 准确性回测”。 | 部分吸收：已有 ETF price、index_based、feeder、qdii_proxy、nav_only、unsupported；未实现 holdings_based、hybrid_bond、hybrid_qdii、benchmark_only、估值准确性。 |
| `Awesome Finance Skills` | 金融 Agent Skill 集合，覆盖新闻、股票、情绪、预测、信号追踪、逻辑链路、研报和搜索。 | Skill 应按能力拆分，可独立安装；每个 skill 有明确输入、输出、安装路径和适配框架。 | fund_agent 可沉淀为 `.codex/skills` 或项目级 `.agents/skills`：fund-screening、portfolio-risk、fund-valuation、daily-report。 | 未实现：当前只是 CLI，不是可安装 Skill 集。 |
| `stock-analytics-skill` | 面向个人投资者的 LLM Skill + CLI，本地获取股票/基金数据，使用 `position.md` 和 `agent.md` 映射场景到技能。 | `position.md` 存个人配置，`agent.md` 存工作流，CLI 输出 `raw` 和 `llm` 两种格式；场景到 Skill 映射清晰。 | fund_agent 适合增加 `position.md`/portfolio schema 文档、LLM-friendly JSON/Markdown 输出和场景路由。 | 概念相似：已有本地 portfolio JSON 和 CLI；未实现 agent.md、Skill 目录、LLM 输出格式、场景路由。 |

## 可复用设计主题

### 1. 数据源层

可借鉴的方向不是“哪个接口函数名”，而是数据层的边界：

- provider 必须和业务逻辑隔离，避免接口变化影响评分/组合/报告。
- live provider 要有缓存、重试、字段契约和降级策略。
- 基金系统需要同时覆盖基金排行、单位净值、历史净值、规模、费率、经理、评级、基金公司、持仓、指数映射、QDII 代理标的。
- AKShare 可作为 Python 主数据源，天天基金 API 可补充基金专有信息。

### 2. Agent 分工

可借鉴的分工应该按产物划分，而不是按“拟人名称”堆角色：

- Data Agent：采集、标准化、缓存、新鲜度。
- Screening Agent：基金候选评分、反追高、候选排序。
- Valuation Agent：估值方法分类、估算、置信度、缺口。
- Risk Agent：组合集中度、相关性、CVaR、费用、赎回约束、QDII 时区/汇率。
- Portfolio Agent：目标权重偏离、再平衡候选、观察/减仓/加仓候选。
- Report Agent：证据标签、风险边界、检查清单、日报。
- Audit Agent：记录每个 Agent 的输入、输出、版本、阈值和投票。

### 3. 报告方式

日报应从“结果列表”升级为“可审计研究包”：

- 首页摘要：候选、持仓风险、数据新鲜度、需要人工核对项。
- 候选表：分数、证据强度、估值方式、置信度、追高风险、数据缺口。
- 持仓表：市值、收益、权重偏离、费用/短赎风险、集中度。
- 风险段：QDII 汇率/时区、数据陈旧、规模过小、单一赛道暴露、相关性上升。
- 核对清单：公告、季报、基金合同、费率、持仓、指数映射、基金公司说明。

### 4. Skill 组织方式

当前项目可以先保持 Python CLI，再向 Skill 化演进：

- `skills/fund-screening/SKILL.md`：触发条件、输入、输出、风险边界。
- `skills/fund-valuation/SKILL.md`：估值方法、数据源、置信度。
- `skills/portfolio-risk/SKILL.md`：持仓文件 schema、风险项、再平衡输出。
- `skills/fund-daily-report/SKILL.md`：日报流程、证据要求、检查清单。
- 每个 Skill 调用同一个本地 CLI 或 Python 包，避免重复业务逻辑。

## 调研来源

- <https://github.com/ZhuLinsen/daily_stock_analysis>
- <https://github.com/muxuuu/serenity-skill>
- <https://akshare.akfamily.xyz/introduction.html>
- <https://github.com/akfamily/akshare>
- <https://kouchao.github.io/TiantianFundApi/>
- <https://github.com/kouchao/TiantianFundApi>
- <https://github.com/24mlight/A_Share_investment_Agent>
- <https://github.com/virattt/ai-hedge-fund>
- <https://github.com/oujingzhou/openfr>
- <https://github.com/Deng-XueCheng/fund-investment-assistant>
- <https://github.com/hkwuks/WealthAgent>
- <https://github.com/RKiding/Awesome-finance-skills>
- <https://github.com/belos-street/stock-analytics-skill>
