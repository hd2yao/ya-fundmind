# V3 Fund Information Platform Delivery Roadmap

## 交付目标

把 v2.6 的本地研究底座收敛为一个面向用户的完整基金信息平台，并发布 `v3.0.0`。V3 的核心不是新增推荐模型，而是补齐基金资料、ETF 行情、产品信息架构和开源交付质量。

当前进度：M1 已发布 `v3.0.0-alpha.1`；下一步进入 M2 Fund Profile Data。

## 版本策略

| Milestone | Git tag | Python package version | 发布含义 |
| --- | --- | --- | --- |
| M1 | `v3.0.0-alpha.1` | `3.0.0a1` | 数据真实性和产品信息架构完成 |
| M2 | `v3.0.0-alpha.2` | `3.0.0a2` | 基金概况、申赎和费率可浏览 |
| M3 | `v3.0.0-beta.1` | `3.0.0b1` | ETF 行情与市场工作区可用 |
| M4 | `v3.0.0-beta.2` | `3.0.0b2` | 持仓、经理、评级和完整详情可用 |
| M5 | `v3.0.0-rc.1` | `3.0.0rc1` | 自选、组合和开源产品表面收口 |
| M6 | `v3.0.0` | `3.0.0` | 全量验收和正式发布 |

## 通用交付规则

每个 Milestone：

1. 从最新 clean `main` 创建 `codex/` 分支和独立 worktree。
2. 先更新当前 Milestone 的 spec/task 映射，再按 TDD 小步实现。
3. 每个独立回滚单元执行相关测试、focused diff review 和 commit。
4. 运行 Python、Web、contract 和真实浏览器验收。
5. 推送分支、创建 PR、等待 CI、修复 P0/P1、合并。
6. 在 clean `main` 上运行验收后创建版本 tag。
7. P0/P1 未清零不得进入下一 Milestone；P2 进入 `docs/backlog/v3-todo.md`。

默认测试不访问真实网络。真实 AKShare smoke 单独执行；对应 Milestone 引入的代表性核心 endpoint 必须在发布前成功并保留 trace。网络失败时不得伪造成功，且该预发布/正式版本保持未发布。

## M1：Product Truth & Information Architecture

### 目标

先消除误导性数据和工程化页面语言，再建立“市场、基金、自选、组合”为一级工作区的产品骨架。

### 必做任务

- 新 V3 domain/view 的缺失收益、净值、估值和持仓市值保持 optional / `null/unknown`。
- 新增 legacy compatibility adapter，保持 `FundRecord`、主评分和旧报告输入不变。
- 组合估值不可用时不计算 0 元、-100% 和虚假权重。
- 新增产品 view model，将用户字段与 diagnostics 分开。
- 调整导航、首页和基金入口；Research/Reports/System 降为二级。
- 用户页面把内部 code 映射为中文解释。
- fixture 新闻默认不作为正式新闻展示。
- 新增独立自选页，第一版只读现有配置。

### 验收标准

- 缺失值回归测试证明 unknown 不会变 0。
- 首页、市场、基金、自选、组合形成闭环。
- 普通页面不显示 schema、内部字段名、raw warning code 和 stack trace。
- v2.6 CLI、daily/weekly、contract、Research Copilot 不回归。
- v2.6 score/risk fixture snapshot 与 M1 结果逐项一致。
- 1440/768/375 浏览器和 accessibility 基础检查通过。

### 不做

- 不接新基金 endpoint。
- 不改主评分/主风险。
- 不允许网页写 watchlist/portfolio。
- 不接真实新闻。

### 产物

- `fund_agent/product_views.py`（预计）
- `web/src/pages/WatchlistPage.tsx`（预计）
- M1 acceptance 和 release report

### CLI

- 保持 `python -m fund_agent.cli product-web --output-dir outputs`
- 允许新增只读产品 API smoke，不新增交易命令

### 测试

- provider/model missing value
- portfolio unknown valuation
- Web navigation/view model
- responsive/a11y
- full pytest/compileall/contract

### 边界

- 允许修改主评分/主风险：否
- 允许输出买卖建议：否

## M2：Fund Profile Data

### 目标

使用 AKShare 已有公募基金接口补齐基金概况、申购赎回和费率，形成真正可用的单基金资料页。

### 必做任务

- 接入并标准化 `fund_name_em`、`fund_overview_em`。
- 将 `fund_name_em`、`fund_open_fund_rank_em`、`fund_etf_spot_em` 定义为 AKShare 基金库并集，记录 raw/mapped/dedup/skipped/type coverage。
- 接入 `fund_purchase_em` 和 `fund_fee_em`。
- 扩展 canonical `FundProfile`、`FundTradingRule`、`FundFee`.
- `fund_name_em` / `fund_purchase_em` 作为 TTL 全量 snapshot；`fund_overview_em` / `fund_fee_em` 作为单基金按需 endpoint，禁止从详情页逐基金调用全量 endpoint。
- 规模区分资产/份额，费率区分费用类型、金额/期限条件、渠道原费率和优惠费率。
- 扩展 SQLite schema、cache TTL、trace 和字段级 warning。
- 新增基金详情标签页：概览、净值与业绩、费率与规则。
- 按需加载单基金资料；全市场列表不批量请求重 endpoint。

### 验收标准

- 任意已索引基金可进入资料页。
- 详情显示公司、经理、成立日、规模、基准、跟踪标的和可用费率。
- 缺字段安全降级且保留字段来源。
- cache fresh/live/stale fallback 均有离线单测。
- 至少 3 种基金类型完成真实 smoke；失败阻断 `alpha.2` 发布。

### 不做

- 不接持仓、评级和经理大全。
- 不做收益预测或同类推荐。
- 不把 Tiantian 设为 daily 默认。

### 产物

- Fund Profile schema/cache/API
- 基金概览与费率页面
- `docs/contracts/fund-profile-v1.md`

### CLI

- 预计新增 `fetch-fund-profile --code`
- 现有 `daily` 默认行为不变

### 测试

- mapping、缺字段、坏行、cache migration、trace、API、Web
- pytest/compileall/contract/Playwright

### 边界

- 允许修改主评分/主风险：否
- 允许输出买卖建议：否

## M3：ETF Market Workspace

### 目标

把现有 ETF spot 和历史能力产品化，并补充指数实时摘要。ETF 行情与普通开放式基金净值明确分开。

### 必做任务

- 扩展 `fund_etf_spot_em` 映射：价格、涨跌、成交、IOPV、折溢价、OHLC、换手等。
- 接入 `fund_etf_hist_em` 的日频历史，contract 保存 `adjust`，默认不复权并在 UI 标注。
- 接入 `stock_zh_index_spot_em` 的主要指数快照。
- 新增 `EtfQuote` 和对应 cache/trace/API。
- 市场页新增 ETF 活跃榜、指数摘要和行情日期。
- ETF 详情新增“交易行情”标签。

### 验收标准

- ETF 快照和历史可查询，普通基金和 LOF 不会误用 ETF 盘口字段。
- 行情时间、source、stale/fallback 清楚但不暴露内部错误。
- 排序和分页在服务端完成。
- 至少 3 只 ETF 和 3 个指数完成 live smoke；失败阻断 `beta.1` 发布。

### 不做

- 不提供秒级推送、Level-2、账户或下单。
- 不承诺 LOF spot/history；LOF 若进入后续范围需独立 endpoint 和 contract。
- 不把 ETF 成交/流入直接转换成推荐。

### 产物

- ETF Quote schema/cache/API
- 市场 ETF 工作区和 ETF 详情
- `docs/contracts/etf-quote-v1.md`

### CLI

- 预计新增 `refresh-etf-market`
- 保持 `market` 和 daily 兼容

### 测试

- mapping、分页、cache、fallback、ETF/开放式基金类型边界
- API/Web/Playwright/full regression

### 边界

- 允许修改主评分/主风险：否
- 允许输出买卖建议：否

## M4：Holdings, Manager, Rating & Performance

### 目标

补齐基金详情的深层资料，使用户不必离开平台即可查看主要公开档案。

### 必做任务

- 接入股票持仓、债券持仓和资产配置。
- 接入基金评级和基金经理数据。
- 接入分红/拆分历史。
- 可选接入 AKShare 风险收益分析；保留来源和样本说明。
- 基金详情新增持仓、经理公司、评级同类、分红拆分标签页。
- 明确持仓报告期和披露滞后。

### 验收标准

- 持仓、资产配置和报告期可展示。
- 经理/评级字段可缺失，不生成正向信号。
- 不同报告期不会被混合为同一时点。
- 详情页不改主 score/risk_issues。

### 不做

- 不推断未披露的实时持仓。
- 不依据评级自动排序推荐。
- 不做真实新闻/舆情。

### 产物

- holding/manager/rating/performance schema/cache/API
- 完整基金详情标签页

### CLI

- 预计扩展 `fetch-fund-profile --include holdings,rating,manager`

### 测试

- report period、mapping、缺字段、重复行、cache、API、Web
- full pytest/contract/Playwright/live optional

### 边界

- 允许修改主评分/主风险：否
- 允许输出买卖建议：否

## M5：Watchlist, Portfolio & Open-source Product Surface

### 目标

完成自选和组合的产品化，并清理开源用户不应看到的示例、调试和本地隐私信息。

### 必做任务

- 自选页提供筛选、分组和最新变化；默认仍由 YAML 管理。
- 组合页区分已估值、未知和过期，不伪造收益。
- 空配置、示例配置和真实配置有明确状态。
- 系统页集中展示数据源、自动运行、cache、trace 和版本。
- README 增加安装、首次运行、数据来源、隐私和免责声明。
- 增加开源发布安全检查，不提交 outputs/cache/个人持仓。
- 设计 tracked `watchlist.example.yaml` / `portfolio.example.yaml` 与 ignored 本地配置迁移；迁移先备份且不得删除当前用户配置，M1-M4 不改现有配置内容。
- 真实新闻未接入时隐藏正式入口；fixture 只在 demo/test 可见。

### 验收标准

- 新用户用 fixture 可启动，用 AKShare 可选 live。
- 自选和组合不会混淆。
- 产品页无内部调试文案或本机绝对路径。
- 默认本地服务只绑定 loopback。
- 打包安装和 clean clone smoke 通过。

### 不做

- 不做账号、多用户、云同步或公网部署。
- 不做网页写入持仓交易。
- 不接券商。

### 产物

- 自选/组合/系统页
- 开源安装与隐私文档
- `v3.0.0-rc.1`

### CLI

- 保持现有 daily/weekly/product-web/ops 命令
- 允许新增 `doctor` 只读诊断命令

### 测试

- clean install、fixture/live optional、privacy/redaction、scheduler、Web
- full Python/React/contract/CLI E2E

### 边界

- 允许修改主评分/主风险：否
- 允许输出买卖建议：否

## M6：V3 Release

### 目标

完成 V3 contract、迁移、兼容、安全、性能、文档和真实运行验收，发布 `v3.0.0`。

### 必做任务

- 冻结 V3 schema 和兼容矩阵。
- 完成 v2.6 -> v3 migration 与 rollback。
- 完成 Python/React/CLI/API/Web/scheduler E2E。
- 完成所有 V3 核心 AKShare endpoint 的真实 smoke、trace 和数据日期核验。
- 完成三视口、accessibility、性能和安全验收。
- 更新 README、CHANGELOG、roadmap、backlog、project structure 和 release report。

### 验收标准

- P0/P1 为 0。
- clean install 和已有用户 upgrade 均可运行。
- daily/weekly 最近运行成功。
- 所有产品页可访问，fixture 不冒充 live。
- 数据缺失不会变成 0、推荐或交易结论。
- tag、commit、版本和文档一致。

### 不做

- 不在 Final 临时加入新闻、多源核验、SaaS 或交易。
- 不以未通过的 live smoke 伪造发布证据。

### 产物

- `docs/releases/v3.0.0-release-report.md`
- `docs/migrations/v2-to-v3.md`
- `v3.0.0` tag

### CLI

- 全量稳定命令清单和 smoke

### 测试

- full pytest、compileall、contract、React、CLI E2E、Playwright、scheduler、clean install

### 边界

- 允许修改主评分/主风险：否
- 允许输出买卖建议：否

## V3 之后

真实新闻/公告、多源核验、公网部署、账号、多用户、推荐实验和交易相关能力不自动进入 V3。必须重新进行 scope、数据许可、合规和安全评审。
