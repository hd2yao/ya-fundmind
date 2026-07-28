# V3 Fund Information Platform Spec

## 背景

v2.6 已具备自动运行、AKShare 基金目录、基金历史净值、指数/板块历史、基金详情、组合、Evidence、Research Copilot 和本地 Product Web。当前系统的主要矛盾已经从“缺少研究底座”变为“基金公开信息不完整、不同基金类型语义混合、产品页暴露工程诊断、页面仍像报告”。

## 目标

把 YA FundMind OS 升级为本地优先的基金/ETF 信息平台，使用户可以：

- 浏览主要指数和板块走势。
- 搜索 AKShare 当前可索引的基金和 ETF。
- 查看单只基金的完整公开档案和历史。
- 对 ETF 查看交易所行情，对开放式基金查看申购赎回和费率。
- 查看自选和组合。
- 在需要时进入研究证据、Copilot、报告和系统诊断。

## 非目标

- 不自动推荐基金。
- 不输出买卖、仓位、止盈止损或收益承诺。
- 不自动交易、不接券商。
- 不提供授权级实时行情、LOF 交易行情或 Level-2。
- 不修改主评分或主风险。
- 不改变 daily 默认 provider。
- 不要求真实新闻、多源核验、公网部署、账号、多用户或移动端。
- 不让前端解析 Markdown 或原始 DataFrame。

## 用户场景

1. 用户打开首页，先看到市场日期、主要指数和基金入口。
2. 用户输入代码/名称，分页搜索 AKShare 当前可索引基金。
3. 用户打开普通开放式基金，查看净值、概况、费率、持仓、经理和评级。
4. 用户打开 ETF，额外查看价格、成交、IOPV、折溢价和历史行情。
5. 用户打开自选，区分“关注”与“持仓”。
6. 用户打开组合，未知估值显示为未知，不出现虚假亏损。
7. 用户只在系统页查看 provider、cache、trace 和内部 warning。
8. 用户在研究区查看证据和 Copilot，但这些不改变基金资料和主结论。

## 验收标准

### 数据真实性

- `AC-001`：V3 provider/domain 缺失收益、净值、价格、规模和费率时保留 optional，V3 产品 JSON 返回 `null`；legacy `FundRecord` 通过显式 adapter 保持旧 contract 和主评分输入。
- `AC-002`：组合当前估值不可用时不生成 0 元、-100% 收益、0 权重或基于这些值的汇总。
- `AC-003`：所有用户可见数值可追溯到结构化字段、日期和来源。
- `AC-004`：fixture、stale、fallback 和 live 状态不会被混淆。

### 产品信息架构

- `AC-005`：一级导航为市场、基金、自选、组合。
- `AC-006`：研究、报告和系统为二级工作区。
- `AC-007`：首页不是 Markdown/报告摘要，首屏提供市场和基金浏览入口。
- `AC-008`：普通页面不显示内部 schema、原始 warning code、stack trace 或本机绝对路径。
- `AC-009`：用户状态文案使用可理解中文，完整诊断仍可在系统页查看。

### 基金目录与基金资料

- `AC-010`：“AKShare 基金库”由 `fund_name_em`、`fund_open_fund_rank_em` 和 `fund_etf_spot_em` 在同一 `as_of` 的规范化并集构成；搜索支持代码、名称、类型、场内/场外、申购状态、排序和分页。
- `AC-033`：目录刷新保存各 endpoint 原始数、映射数、去重数、跳过数和类型覆盖率；不同份额代码分别保留，非法代码隔离。
- `AC-011`：任意已索引基金可进入稳定详情 URL。
- `AC-012`：Fund Profile 覆盖概况、规模、公司、经理、托管、基准、跟踪标的、申赎和主要费率。
- `AC-013`：资料按需加载、cache-first；单个 endpoint 失败不阻断已获得数据。
- `AC-014`：字段级 source/as_of/stale 在 diagnostics 可追踪。

### 净值与业绩

- `AC-015`：基金详情显示单位/累计净值和 1m/3m/6m/1y/all 历史。
- `AC-016`：短样本、缺点和数据日期有明确状态，不伪造连续曲线。
- `AC-017`：持仓、评级和同类数据的报告期/样本范围清楚。

### ETF 与市场

- `AC-018`：ETF 可显示价格、涨跌、成交、IOPV、折溢价和 OHLC 等可用行情；历史 contract 保存 `adjust`，V3 默认不复权并在 UI 标注。
- `AC-019`：普通开放式基金不显示买一/卖一、成交或盘口。
- `AC-020`：主要指数提供快照和历史，行业板块提供目录、榜单和历史。
- `AC-021`：ETF/指数 live 失败时可 fallback，并显示数据日期。
- `AC-022`：系统不提供订单、账户、下单或可交易数量。

### 自选、组合和研究

- `AC-023`：自选明确来自 `configs/watchlist.yaml`，与 AKShare 基金库和持仓分开。
- `AC-024`：组合明确来自 `configs/portfolio.yaml`，空/示例/真实配置有不同状态。
- `AC-025`：Research Copilot、Evidence、Review 和 Reports 保持可用但不影响基金资料。
- `AC-026`：真实新闻未接入时，fixture 不以正式新闻入口出现。

### 兼容、开源和发布

- `AC-027`：v2.6 JSON contract、daily/weekly、CLI、Skill/MCP 和历史 outputs 兼容。
- `AC-028`：默认 pytest/CI 无真实网络；引入核心 endpoint 的 alpha/beta/Final 发布必须在可联网环境完成代表性 live smoke 并保留 trace，失败即阻断该版本发布且不得伪造成功。
- `AC-029`：1440/768/375 无页面级重叠和溢出，基础 accessibility 通过。
- `AC-030`：clean install、升级、回滚、scheduler 和隐私检查通过。
- `AC-031`：M5 提供 tracked `*.example.yaml` 与 ignored 本地配置迁移方案；迁移不得删除当前用户配置，开源仓库不新增 outputs、cache、用户持仓、日志或 secret。
- `AC-032`：`main_score_changed=false`、`main_risk_changed=false`，并以 v2.6 fixture/live snapshot 回归证明 legacy score/risk 未变化；无买卖建议和交易动作。

## 约束

- Python 3.10+，React/Vite 前端沿用现有项目。
- AKShare 是 V3 主 live provider，接口不稳定必须 fail-soft。
- 全量 endpoint 使用 TTL snapshot，单基金 endpoint 才按需加载；详情请求不得逐基金调用全量 endpoint。
- SQLite migration 前向、可重复、不可删除用户数据。
- API 只返回产品 view model 或明确 diagnostics contract。
- Product Web 默认只绑定 `127.0.0.1`。

## 决策

- 采用“基金信息平台”而不是“报告工作台”或“交易终端”。
- V3 使用独立 schema，不破坏 v2.6 contract。
- 先完成 AKShare 单源功能，不让多源核验阻塞核心。
- 新闻/公告真实接入不作为 V3 核心发布 gate。
