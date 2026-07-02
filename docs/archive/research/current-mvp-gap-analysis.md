# Current MVP Gap Analysis

调研日期：2026-06-22

本文对照当前 `fund_agent` 代码，判断每个 MVP 设计来自参考项目、只是概念相似，还是自行实现。

## 当前 MVP 模块图

```text
fund_agent/
  models.py      -> FundRecord / ScoredFund / ValuationResult
  providers.py   -> FixtureProvider / AkshareProvider / portfolio loader
  scoring.py     -> fund ranking and anti-sprint scoring
  valuation.py   -> valuation method classification
  portfolio.py   -> holding value, drift, concentration, stale-data checks
  agents.py      -> deterministic agent-style orchestration
  report.py      -> Markdown and simple HTML report
  cli.py         -> demo / screen / portfolio commands
```

## 设计来源判断

| 当前模块/设计 | 当前实现 | 参考来源影响 | 判断 |
| --- | --- | --- | --- |
| 本地 Python 包 + CLI | `fund_agent.cli` 提供 `demo`、`screen`、`portfolio`，默认 fixture，无密钥。 | `daily_stock_analysis` 的本地运行/定时方向，`OpenFR` 的轻量 CLI，`stock-analytics-skill` 的本地 CLI。 | 自行实现，架构思想来自参考项目。 |
| FixtureProvider | `data/fixtures/funds.json` 保证 demo 和测试无网络。 | `daily_stock_analysis` 的降级意识，AKShare/天天基金接口不稳定的经验。 | 自行实现，吸收了“可降级数据源”思想。 |
| AkshareProvider | 可选 live provider，未安装 `akshare` 时抛出明确错误。 | `akshare` 和多个参考项目使用 AKShare 作为财经数据入口。 | 部分吸收，当前只是最小 provider，不是完整数据层。 |
| FundRecord 标准模型 | `FundRecord` 包含 code/name/category/nav/returns/scale/fee/exchange fields。 | AKShare 和基金项目的字段抽象需求。 | 自行实现，字段覆盖仍较少。 |
| 反追高评分 | `score_fund()` 用收益质量、趋势一致性、动量、风险调整、规模和 anti_sprint_penalty 排序。 | `fund-investment-assistant` 的 smart_score、反追高和多周期收益思想。 | 明显吸收设计，公式为本项目自行实现。 |
| 估值分类 | `classify_valuation()` 区分 `etf_price`、`feeder`、`qdii_proxy`、`index_based`、`nav_only`、`unsupported`。 | `WealthAgent` 的估值策略分层。 | 明显吸收设计，当前实现是 MVP 简化版。 |
| 组合分析 | `analyze_portfolio()` 计算市值、成本、浮盈、权重、目标偏离、集中度、数据陈旧。 | `fund-investment-assistant` 的持仓建议/组合风险，`stock-analytics-skill` 的持仓配置。 | 部分吸收，缺少高级风险和费用。 |
| Agent-style orchestration | `run_research()` 线性执行 Data/Screening/Valuation/Risk/Portfolio/Report trace。 | `ai-hedge-fund`、`A_Share_investment_Agent`、`OpenFR` 的角色分工。 | 概念相似，不是完整多 Agent。 |
| 报告输出 | Markdown + HTML，含免责声明、Agent 摘要、候选表、估值缺口、组合概览、风险提示、下一步核对。 | `daily_stock_analysis` 的日报/检查清单，`serenity-skill` 的证据和核验，基金项目的持仓报告。 | 部分吸收，渲染代码自行实现且较简洁。 |
| 证据标签 | `score_fund()` 输出 `Medium`、`Needs checking`、`Weak`。 | `serenity-skill` 的证据强度和可核验研究边界。 | 概念吸收，当前只按字段缺失粗略判定。 |
| 风险边界 | README 和报告均声明不构成投资建议，不自动交易。 | 几乎所有金融 Agent 参考项目都有研究/教育用途边界。 | 已实现，但还缺少更细的高风险场景规则。 |
| 测试覆盖 | pytest 覆盖评分、估值、组合、provider、报告、CLI。 | `TiantianFundApi` 和多数项目强调测试，但当前测试是本项目 TDD 结果。 | 自行实现。 |

## 已吸收的设计

### 1. 基金优先而非个股优先

MVP 范围明确只覆盖基金和 ETF，不做个股推荐、不接券商、不自动下单。这个定位吸收了 `fund-investment-assistant` 和 `WealthAgent` 的基金系统方向，也避免了 `daily_stock_analysis`、`A_Share_investment_Agent`、`ai-hedge-fund` 中更复杂的个股交易建议表述。

已实现位置：

- `README.md`
- `docs/plans/2026-06-22-fund-etf-agent-design.md`
- `fund_agent/models.py`
- `fund_agent/scoring.py`
- `fund_agent/valuation.py`

### 2. 可运行本地 MVP

当前默认 fixture 数据可跑通 demo，不需要 API key。这一点和 `serenity-skill` 的本地脚本、`stock-analytics-skill` 的本地 CLI、`OpenFR` 的轻量 CLI 方向一致。

已实现位置：

- `data/fixtures/funds.json`
- `data/portfolio.example.json`
- `fund_agent/providers.py`
- `fund_agent/cli.py`

### 3. 反追高评分

当前评分不是简单按近一年收益排序，而是加入趋势一致性、动量确认、风险调整、规模约束和短期冲刺惩罚。这是从 `fund-investment-assistant` 最直接吸收的设计点。

已实现位置：

- `fund_agent/scoring.py`
- `tests/test_scoring.py`

缺口：

- 没有参数配置文件。
- 没有市场状态自适应。
- 没有基准超额收益。
- 没有回测证明评分有效性。

### 4. 估值方法先分类再输出

当前不会对所有基金套同一个估值逻辑，而是先识别场内 ETF/LOF、ETF 联接、QDII、指数/NAV-only 和 unsupported。这来自 `WealthAgent` 的估值策略分层思想。

已实现位置：

- `fund_agent/valuation.py`
- `tests/test_valuation.py`

缺口：

- ETF 联接还没有用目标 ETF 实时估算。
- QDII 还没有汇率、海外市场时区、代理 ETF 涨跌幅。
- 主动基金没有 holdings-based 估值。
- 债券/偏债基金没有利率和债券组合估值。
- 没有估值准确性追踪。

### 5. 持仓风险日报

当前能读取本地持仓，计算市值、浮盈、目标权重偏离、集中度和数据陈旧。这吸收了 `fund-investment-assistant` 的组合管理方向和 `stock-analytics-skill` 的 position 配置方向。

已实现位置：

- `data/portfolio.example.json`
- `fund_agent/portfolio.py`
- `fund_agent/report.py`

缺口：

- 没有现金仓位纳入总资产。
- 没有费用、A/C 类、短赎费。
- 没有相关性矩阵、CVaR、风险平价、有效 N。
- 没有赛道/基金公司/经理集中度。
- 没有再平衡候选动作分级。

### 6. Agent 运行摘要而非真实多 Agent

当前 `DataAgent`、`ScreeningAgent`、`ValuationAgent` 等只是 trace 名称和线性 orchestration，并没有并行 Agent、LLM、LangGraph、投票、辩论或状态 API。它更像“保留未来 Agent 接口的确定性 orchestrator”。

已实现位置：

- `fund_agent/agents.py`

缺口：

- 没有中间产物持久化。
- 没有每个 Agent 的输入/输出 schema。
- 没有 Agent 投票记录。
- 没有可插拔 LLM adapter。
- 没有 LangGraph 或状态图。

## 完全没有吸收的设计

| 未实现方向 | 来源项目 | 为什么重要 | 进入路线 |
| --- | --- | --- | --- |
| 天天基金数据层 | `TiantianFundApi`、`stock-analytics-skill` | 基金详情、历史净值、评级、经理、基金公司、排行补充。 | 新增 provider 和字段契约，先只读，不影响业务模块。 |
| 数据缓存/重试/熔断 | `daily_stock_analysis`、`OpenFR`、`fund-investment-assistant` | 真实数据源会失败或变字段。 | provider 层加 cache store 和 stale warnings。 |
| 配置驱动参数 | `fund-investment-assistant` | 阈值、权重、风险偏好不能写死。 | `config/parameters.yaml` 或 pyproject 配置。 |
| 费用感知 | `fund-investment-assistant` | A/C 类和短赎费会改变建议。 | 在 `PortfolioHolding` 和 fund metadata 中加入费率/持有期规则。 |
| 相关性/CVaR/风险平价 | `fund-investment-assistant` | 组合层风险不能只看单只集中度。 | 需要历史净值数据后实现。 |
| Skill 包 | `serenity-skill`、`Awesome Finance Skills`、`stock-analytics-skill` | 让外部 Agent 能稳定调用基金能力。 | 新增 `skills/` 或 `.agents/skills/`，调用现有 CLI。 |
| 证据来源分级 | `serenity-skill` | 研究报告需要说明证据强弱，不只是字段完整性。 | 建立 evidence schema 和 source path。 |
| 多 Agent 辩论/投票 | `OpenFR`、`A_Share_investment_Agent`、`ai-hedge-fund` | 有助于暴露反方理由和风险，但复杂度高。 | 在确定性核心稳定后做可选 adapter。 |
| Web/API 工作台 | `daily_stock_analysis`、`WealthAgent`、`A_Share_investment_Agent` | 管理持仓、查看历史报告、刷新估值。 | FastAPI + 简单前端，放在后续阶段。 |
| 定时推送 | `daily_stock_analysis`、`fund-investment-assistant` | 日报系统最终需要自动运行和提醒。 | 先 GitHub Actions/cron，再通知渠道。 |

## 当前 MVP 的主要风险

1. 数据过少：fixture 只有 6 只基金，live provider 只用一个 AKShare 排行接口，无法支撑可靠研究。
2. 评分不可校验：反追高公式有测试，但没有历史回测和基准比较。
3. 估值过浅：大多数方法实际仍返回最新净值，尚未利用指数、持仓、汇率和实时行情计算。
4. 风险维度不足：组合风险只覆盖目标偏离、集中度和数据陈旧。
5. Agent 名称容易误导：当前不是 LLM 多 Agent，只是 deterministic orchestrator。
6. 报告证据不足：报告有证据标签，但没有列出具体数据源、更新时间和核验路径。

## 结论

当前 MVP 是一个合理的本地骨架，适合作为后续基金 Agent 系统的核心域逻辑。它的优势是边界清晰、可测试、无需密钥、没有交易执行风险；短板是数据层、估值深度、组合风险、审计能力和 Skill 化都还停留在第一版。

下一步不应优先开发炫目的多 Agent，而应先把数据源、字段契约、估值方法、组合风险和报告审计补扎实。
