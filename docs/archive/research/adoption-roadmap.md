# Adoption Roadmap

调研日期：2026-06-22

本文建立“参考项目 -> 可借鉴设计 -> 当前项目模块 -> 是否已实现 -> 后续任务”的映射，并给出下一阶段最值得落地的 10 个任务。

## 映射表

| 参考项目 | 可借鉴设计 | 当前项目模块 | 是否已实现 | 后续任务 |
| --- | --- | --- | --- | --- |
| `ZhuLinsen/daily_stock_analysis` | 每日分析、Markdown/HTML 报告、Web 工作台、历史报告、推送、数据降级。 | `fund_agent/report.py`、`fund_agent/cli.py` | 部分实现：已有报告和 CLI；未有 Web、推送、历史报告、自动任务。 | 先补报告元数据和历史输出目录，再做 cron/GitHub Actions 推送。 |
| `ZhuLinsen/daily_stock_analysis` | 多源行情、新闻、公告、基本面，市场边界降级。 | `fund_agent/providers.py` | 极简实现：只有 fixture 和 AKShare 排行。 | 增加 provider contract、cache、stale warnings、source priority。 |
| `muxuuu/serenity-skill` | 证据链、证据强度、失败条件、下一步核验、研究边界。 | `fund_agent/scoring.py`、`fund_agent/report.py` | 概念实现：只有粗略 `evidence_label` 和核对清单。 | 建立 `EvidenceItem`、source strength、failure condition 和 report section。 |
| `muxuuu/serenity-skill` | Skill 包结构、本地 scorecard、Agent 可安装能力。 | 暂无 | 未实现。 | 设计 `skills/fund-screening`、`skills/fund-valuation`、`skills/portfolio-risk`。 |
| `akfamily/akshare` | Python 财经数据接口、基金排行、历史数据、接口文档和字段维护。 | `fund_agent/providers.py` | 部分实现：只有 `fund_open_fund_rank_em` 最小读取。 | 扩展 AKShare provider，记录字段映射和接口 smoke test。 |
| `kouchao/TiantianFundApi` | 天天基金净值、历史净值、基金详情、字段可读性和测试。 | 暂无 | 未实现。 | 新增 `TiantianFundProvider`，先接历史净值和基金详情。 |
| `24mlight/A_Share_investment_Agent` | 多角色分析、LLM 评审、情绪新闻、后端状态 API。 | `fund_agent/agents.py` | 概念相似：只有 deterministic trace。 | 不急于引入 LLM；先持久化 Agent 中间产物和状态。 |
| `ai-hedge-fund` | 估值/情绪/基本面/技术信号、Risk Manager、Portfolio Manager、无真实交易。 | `fund_agent/agents.py`、`fund_agent/portfolio.py` | 部分实现：有估值/风险/组合角色，但没有多信号和仓位限制。 | 增加信号 schema，让 Portfolio Agent 汇总结构化信号。 |
| `OpenFR` | LangGraph 三阶段流程、牛熊辩论、三方风险评估、节点耗时、fallback/cache。 | `fund_agent/agents.py` | 未实现真实图编排。 | 先加 node timing 和 intermediate report，再评估 LangGraph。 |
| `fund-investment-assistant` | 6 Agent、smart_score、持仓建议、费用感知、组合风险、动态权重、审计追踪。 | `fund_agent/scoring.py`、`fund_agent/portfolio.py` | 部分实现：反追高、持仓价值、偏离、集中度；缺少高级风险。 | 优先补费用、相关性/CVaR、配置驱动、审计 trace。 |
| `WealthAgent` | 基金估值类型：实时价格、指数、持仓、债券混合、QDII 混合、benchmark-only、估值准确性。 | `fund_agent/valuation.py` | 部分实现：分类已起步；计算仍浅。 | 增加估值输入数据和准确性 tracking。 |
| `Awesome Finance Skills` | 新闻、股票、情绪、预测、信号追踪、逻辑链路、研报、搜索等 Skill 拆分。 | 暂无 | 未实现。 | 不直接复制；借鉴 skill 颗粒度和安装约定。 |
| `stock-analytics-skill` | `position.md` + `agent.md` 场景路由、本地 CLI 输出 raw/llm、基金/股票数据查询。 | `data/portfolio.example.json`、`fund_agent/cli.py` | 部分实现：有 portfolio JSON 和 CLI；没有 agent.md、LLM 输出格式。 | 增加 portfolio schema 文档、`--format json|markdown|llm`、场景说明。 |

## 下一阶段 10 个优先任务

### P1. 建立数据字段契约和 provider contract

目标：把 `FundRecord` 需要的字段、来源、更新时间、缺失策略写成文档和测试。

原因：后续接 AKShare/天天基金前，先约定内部字段，避免外部接口结构污染业务层。

验收：

- 新增 `docs/research/data-contract.md` 或 `docs/specs/fund-data-contract.md`。
- provider 测试覆盖字段缺失、百分号、空值、日期、新鲜度。
- 报告能显示数据源和更新时间。

### P2. 增加缓存和数据新鲜度机制

目标：在 provider 层加入 JSON cache、TTL、stale warning 和 live failure fallback。

原因：AKShare、天天基金和网页接口都可能失败，基金日报必须能“带警告完成”。

验收：

- `FixtureProvider`、`AkshareProvider` 使用统一 provider interface。
- live provider 失败时可回退缓存。
- 报告展示 stale/cache/source 状态。

### P3. 扩展 AKShare live provider

目标：从单一排行接口扩展到基金基础信息、历史净值、规模、费率等可用字段。

原因：当前评分和组合风险缺少历史净值和费用输入。

验收：

- provider 能返回至少 1m/3m/6m/1y 收益、净值日期、规模、基金类型。
- live smoke test 可跳过但有明确命令。
- 业务层不直接 import akshare。

### P4. 新增天天基金 provider

目标：接入天天基金基金详情、历史净值、基金经理/公司、评级或同类排名等信息。

原因：基金系统需要基金专有数据，AKShare 不一定覆盖完整。

验收：

- 新增 provider 类和单元测试，用录制/fixture 数据验证字段映射。
- 输出字段统一为 `FundRecord` 或扩展 metadata。
- 文档标明 unofficial API 风险和频率限制。

### P5. 估值模块升级为可解释估值引擎

目标：从分类返回净值，升级为 method-specific 计算和数据缺口说明。

原因：`WealthAgent` 的价值在于“估值方法随基金类型变化”，当前只是第一层分类。

验收：

- ETF/LOF 使用价格 + NAV 折溢价。
- ETF 联接使用目标 ETF proxy 估算。
- QDII 使用 proxy + 汇率/时区说明。
- 主动基金先支持 benchmark-only，再逐步 holdings-based。
- 每个 `ValuationResult` 有 confidence、source、missing_fields。

### P6. 组合风险升级：费用、相关性、CVaR、有效 N

目标：补齐基金组合真正需要的风险维度。

原因：当前只看单只集中度，容易漏掉同赛道/高相关基金的集中风险。

验收：

- 持仓分析纳入现金。
- A/C 类、持有天数、短赎费、管理费/托管费提示。
- 用历史净值计算相关性矩阵和简单 VaR/CVaR。
- 输出有效 N、类别集中度、基金公司/经理集中度。

### P7. 评分参数配置化和评分审计

目标：把收益权重、惩罚阈值、规模阈值、风险偏好从代码移到配置。

原因：评分公式会持续迭代，硬编码不利于解释和回测。

验收：

- 默认参数文件可被 CLI 指定。
- 报告显示评分版本和关键阈值。
- 每个候选输出 score breakdown 和扣分原因。

### P8. 报告升级为可审计研究包

目标：报告不只展示结果，还展示来源、缺口、反方理由、核验路径和下一步动作。

原因：参考项目共同强调研究边界和证据链，基金系统尤其需要避免“黑箱建议”。

验收：

- 报告新增数据源/更新时间/置信度总览。
- 每个候选有“为什么优先研究”和“什么情况说明判断错了”。
- 风险提示按 High/Medium/Low 分组。
- Markdown 和 HTML 保持一致。

### P9. Skill 化但复用现有 CLI

目标：新增 Agent Skill 包，让外部 Codex/Claude/OpenClaw 类 Agent 可调用。

原因：用户最初明确关注 Agent/Skill，当前项目只有 CLI，尚不能作为标准 skill 使用。

验收：

- `skills/fund-screening/SKILL.md`
- `skills/fund-valuation/SKILL.md`
- `skills/portfolio-risk/SKILL.md`
- `skills/fund-daily-report/SKILL.md`
- 每个 Skill 指向现有 CLI，不重复业务逻辑。

### P10. Agent trace 持久化和中间产物

目标：先做可观察 workflow，再考虑 LangGraph/LLM 多 Agent。

原因：当前直接上多 Agent 容易掩盖数据和估值缺口。先记录每个阶段输入、输出、耗时、警告、版本。

验收：

- 每次 run 生成 `outputs/runs/<date>/trace.json`。
- trace 包含 Data/Screening/Valuation/Risk/Portfolio/Report 节点。
- 报告链接或列出 trace 摘要。
- 后续可无痛接 LangGraph 或 LLM adapter。

## 推荐落地顺序

```text
数据契约
  -> 缓存和 provider 稳定性
  -> AKShare/天天基金数据补齐
  -> 估值引擎
  -> 组合风险
  -> 评分配置化
  -> 可审计报告
  -> Skill 包
  -> trace 持久化
  -> 可选 LLM/LangGraph
```

## 暂不建议立即做的事

- 不建议立即做 Web 工作台：当前核心数据和估值还不够扎实。
- 不建议立即上真实多 Agent 辩论：没有足够结构化数据时，辩论会变成文本包装。
- 不建议加入自动交易或券商接口：超出研究助手边界，也会显著增加合规风险。
- 不建议直接复制参考项目代码：许可证、工程风格、数据结构和目标市场都不完全一致。

## 下一阶段成功标准

下一阶段完成后，系统应达到：

- 每条基金数据都知道来自哪里、何时更新、缺哪些字段。
- 每个候选分数都能解释“加分/扣分/证据强度/追高风险”。
- 每个估值都有方法、公式、置信度、缺口和适用边界。
- 每个持仓风险都能定位到集中度、相关性、费用、数据新鲜度或产品类型。
- 报告可被人复核，也可被 Agent 作为下一轮研究输入。
