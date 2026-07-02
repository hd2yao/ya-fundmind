# V1 Delivery Roadmap

## Roadmap 原则

从本文件开始，YA FundMind OS 不再无限追加 Phase。V1 收敛为 6 个 Milestone。每个 Milestone 都必须保持系统可运行、测试可通过、输出边界清晰。

V1 全局边界：

- 不自动交易。
- 不输出买卖建议。
- 不承诺收益。
- 不接券商。
- 默认测试不依赖真实网络。
- Agent、Skill、MCP、LLM 放到 V2。
- 主评分/主风险只有在 Milestone 明确允许时才能修改；默认不允许。

## M1: Fund Detail 通用化收尾

### 目标

把 Phase 12 的 Fund Detail 从“自选池 drilldown”补齐为 V1 可复用详情层，使单只基金、自选池、dashboard 和 daily ops 都能稳定读取同一份详情输出。

### 必做任务

- 补齐 Fund Detail 对 AKShare market artifact、Tiantian NAV summary、cache fallback 的读取优先级文档和测试。
- 明确自选池基金、持仓基金、市场候选基金的标记方式。
- 完善 dashboard fund detail 页面结构，但保持静态本地页面。
- 保证 watchlist-detail 在 daily ops 中失败不阻塞主流程。
- 补齐缺字段、stale cache、missing market record 的数据质量展示。

### 验收标准

- `fund-detail --code` 可生成单只 JSON/Markdown。
- `watchlist-detail` 可生成自选池总表和每只基金详情。
- `outputs/dashboard/funds.html` 和 `outputs/dashboard/funds/{code}.html` 正常生成。
- `ops-status` 和 `latest_summary.md` 能展示 fund detail 状态。
- 缺字段不会崩溃，必须进入 `missing_fields` 和 `data_quality_warnings`。

### 不做什么

- 不做新闻/公告/舆情。
- 不做 historical backfill。
- 不改主评分。
- 不改主风险。
- 不输出买卖建议。

### 产物路径

- `outputs/fund_details/fund_detail_{code}.json`
- `outputs/fund_details/fund_detail_{code}.md`
- `outputs/fund_details/watchlist_fund_details.json`
- `outputs/fund_details/watchlist_fund_details.md`
- `outputs/dashboard/funds.html`
- `outputs/dashboard/funds/{code}.html`

### CLI 命令

```bash
python -m fund_agent.cli fund-detail --code 021511 --output-dir outputs
python -m fund_agent.cli watchlist-detail --watchlist-file configs/watchlist.yaml --output-dir outputs
python -m fund_agent.cli generate-evidence-dashboard --runs-dir outputs/runs --review-state outputs/manual_review_state.json --output-dir outputs/dashboard --days 30
```

### 测试要求

- Fund Detail builder 单元测试。
- CLI 输出测试。
- Dashboard 页面测试。
- Ops status/latest summary 测试。
- Daily ops 脚本集成测试。

### 是否允许修改主评分/主风险

不允许。

### 是否允许输出买卖建议

不允许。

## M2: Historical Backfill 历史回填层

### 目标

允许把过去一段时间的 daily research 所需基础 artifact 补齐，用于市场趋势、信号稳定性和 review gate 观察。Backfill 只补证据，不做回测，不做收益归因。

### 必做任务

- 新增本地 backfill 命令，按日期范围生成 run bundle。
- 支持 fixture/cache/可选 live provider 的清晰模式。
- 对每个日期写入 run metadata、contract validation 状态、数据质量状态。
- 明确 backfill 与真实 daily run 的区别。
- 防止覆盖已有 run，除非显式 `--overwrite`。

### 验收标准

- 可生成 `outputs/runs/YYYY-MM-DD` 历史运行包。
- 缺少真实历史数据时不会伪造成功。
- `evaluate-long-horizon-stability` 能读取 backfill run。
- `market-trend` 能读取历史 market snapshots。
- 所有 backfill 产物可被 ops-status/dashboard 识别。

### 不做什么

- 不做交易模拟。
- 不做收益回测。
- 不把 backfill 结果自动接入主评分。
- 不伪造历史真实数据。

### 产物路径

- `outputs/runs/YYYY-MM-DD/`
- `outputs/backfill/backfill_report.json`
- `outputs/backfill/backfill_summary.md`

### CLI 命令

```bash
python -m fund_agent.cli backfill-research --start-date 2026-06-01 --end-date 2026-06-30 --provider fixture --output-dir outputs
python -m fund_agent.cli evaluate-long-horizon-stability --runs-dir outputs/runs --output outputs/long_horizon_stability.json
```

### 测试要求

- 日期范围解析测试。
- 不覆盖已有 run 测试。
- 缺数据降级测试。
- run bundle contract 测试。
- dashboard/ops 读取测试。

### 是否允许修改主评分/主风险

不允许。

### 是否允许输出买卖建议

不允许。

## M3: Portfolio Analysis 组合分析层

### 目标

把当前持仓从“配置读取”升级为组合观察层，展示仓位、集中度、主题暴露、持仓风险和与自选池/市场主题的关系。

### 必做任务

- 读取 `configs/portfolio.yaml` 并生成 portfolio detail JSON/Markdown。
- 汇总持仓市值、权重、盈亏、主题暴露、数据质量。
- 将持仓基金与 Fund Detail、Market Intelligence、Market Trend 关联。
- 在 dashboard 增加 portfolio 页面。
- 在 latest summary 增加 portfolio 状态摘要。

### 验收标准

- `portfolio-analysis` 可稳定生成组合分析输出。
- 持仓为空、字段缺失、cache stale 都能安全降级。
- dashboard 能展示组合权重、集中度和主题暴露。
- 输出明确是研究辅助，不含买卖建议。

### 不做什么

- 不做自动调仓。
- 不做目标仓位推荐。
- 不输出买卖点。
- 不接券商账户。

### 产物路径

- `outputs/portfolio/portfolio_analysis.json`
- `outputs/portfolio/portfolio_analysis.md`
- `outputs/dashboard/portfolio.html`
- `outputs/runs/YYYY-MM-DD/portfolio_analysis.json`

### CLI 命令

```bash
python -m fund_agent.cli portfolio-analysis --portfolio-config configs/portfolio.yaml --output-dir outputs
```

### 测试要求

- portfolio YAML 读取测试。
- 空持仓测试。
- 主题暴露聚合测试。
- stale/fallback 数据质量测试。
- dashboard/ops 集成测试。

### 是否允许修改主评分/主风险

不允许。

### 是否允许输出买卖建议

不允许。

## M4: News / Announcement Evidence 新闻公告证据层

### 目标

新增新闻和公告证据收集层，辅助解释市场主题和基金关注点。该层只收集、归类、引用证据，不做舆情预测，不给买卖建议。

### 必做任务

- 定义 news evidence 数据契约。
- 支持本地 mock/fixture 新闻源，真实源可选。
- 对新闻/公告按主题、基金代码、来源、发布时间、可信度归类。
- 在 market/fund detail/dashboard 中展示证据引用。
- 记录 source、published_at、fetched_at、url/title/summary。

### 验收标准

- 默认测试不依赖真实网络。
- 新闻源失败不阻塞 daily ops。
- 每条证据有来源和时间。
- dashboard 可以查看主题/基金相关证据。
- 不输出“利好即买入”等自动结论。

### 不做什么

- 不做舆情打分。
- 不做 LLM 自动总结。
- 不做新闻交易策略。
- 不抓取需要登录或违反来源规则的数据。

### 产物路径

- `outputs/news/news_evidence.json`
- `outputs/news/news_evidence.md`
- `outputs/dashboard/news.html`
- `outputs/runs/YYYY-MM-DD/news_evidence.json`

### CLI 命令

```bash
python -m fund_agent.cli collect-news-evidence --output-dir outputs
```

### 测试要求

- fixture 新闻源测试。
- 来源字段完整性测试。
- 缺来源/坏行隔离测试。
- dashboard 展示测试。
- daily ops warning-only 测试。

### 是否允许修改主评分/主风险

不允许。

### 是否允许输出买卖建议

不允许。

## M5: Web Console v1

### 目标

把当前静态 dashboard 收敛为本地 Web Console v1，提供更清晰的导航、筛选、详情页和人工审核入口。Web Console 只读本地 JSON artifact，不引入 SaaS 和后端服务。

### 必做任务

- 设计本地静态/轻量 Web Console 信息架构。
- 整合 market、trend、fund detail、portfolio、news、review、ops status。
- 支持基础筛选、排序、折叠详情、链接到原始 JSON。
- 保持本地文件可打开或本地静态服务可运行。
- 明确下游读取 JSON，不解析 Markdown。

### 验收标准

- `outputs/dashboard/index.html` 是真正可导航工作台。
- 各模块可点击、可筛选、可查看详情。
- 页面不改变报告主结论。
- Playwright 或等价检查确认关键页面非空、链接可用。

### 不做什么

- 不做登录。
- 不做 SaaS。
- 不做移动端。
- 不做 MCP/LLM/Agent 问答。
- 不做交易按钮。

### 产物路径

- `outputs/dashboard/index.html`
- `outputs/dashboard/market.html`
- `outputs/dashboard/funds.html`
- `outputs/dashboard/portfolio.html`
- `outputs/dashboard/news.html`
- `outputs/dashboard/review.html`

### CLI 命令

```bash
python -m fund_agent.cli generate-evidence-dashboard --runs-dir outputs/runs --review-state outputs/manual_review_state.json --output-dir outputs/dashboard --days 30
```

### 测试要求

- Dashboard HTML 生成测试。
- 关键页面存在测试。
- 页面链接测试。
- artifact 缺失降级测试。
- 可选 Playwright smoke。

### 是否允许修改主评分/主风险

不允许。

### 是否允许输出买卖建议

不允许。

## M6: V1 Release 收口

### 目标

冻结 V1 输出契约、运行流程、文档和本地安装方式，形成可交付的个人基金/ETF投研工作台。

### 必做任务

- 完成 V1 contract review。
- 完成 README、安装说明、运行说明、故障排查说明。
- 检查 daily/weekly scheduler 安装和卸载流程。
- 跑完整 demo、fixture daily、可选 AKShare smoke、可选 Tiantian smoke。
- 清理 V1 backlog，确认 V2 items 不阻塞。
- 打 V1 release tag。

### 验收标准

- 新机器按 README 能完成本地运行。
- daily/weekly ops 可安装、查看状态、卸载。
- `outputs/latest_summary.md`、`outputs/dashboard/index.html`、`outputs/runs/YYYY-MM-DD` 稳定生成。
- 默认测试和 CI 通过。
- V1 边界文档明确。

### 不做什么

- 不在 V1 末尾临时接入 Agent/LLM/MCP。
- 不临时接券商。
- 不临时修改主评分/主风险。
- 不加入自动交易。

### 产物路径

- `README.md`
- `docs/architecture/v1-system-architecture.md`
- `docs/roadmap/v1-delivery-roadmap.md`
- `docs/ops/*`
- `outputs/latest_summary.md`
- `outputs/dashboard/index.html`

### CLI 命令

```bash
python -m pytest -q
python -m compileall -q fund_agent
scripts/run_daily_ops.sh
scripts/run_weekly_ops.sh
python -m fund_agent.cli ops-status --output-dir outputs --json-output outputs/ops_status.json --write-latest-summary
```

### 测试要求

- 全量 pytest。
- compileall。
- contract validation。
- ops scripts smoke。
- dashboard smoke。

### 是否允许修改主评分/主风险

默认不允许。只有在单独批准的主模型变更任务中才允许。

### 是否允许输出买卖建议

不允许。

## 当前定位

当前项目位于 M1 前：Phase 12 已完成 Fund Detail 起点，但还需要按 M1 做通用化收尾，然后再进入 M2 Historical Backfill。
