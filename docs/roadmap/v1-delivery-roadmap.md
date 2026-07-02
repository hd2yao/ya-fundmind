# V1 Delivery Roadmap

## Autonomous V1 Delivery Mode

YA FundMind OS v1 后续只按 M1 -> M2 -> M3 -> M4 -> M5 -> M6 推进，不再新增 Phase 13 / Phase 14 / Phase 15 这类无限阶段。

每个 Milestone 规则：

- 只实现该 Milestone 的内容。
- 完成后必须自验。
- 自验通过后可以进入下一个 Milestone。
- 自验不通过时，只允许在当前 Milestone 内修复。
- P0 / P1 问题必须修复。
- P2 优化项写入 `docs/backlog/v1-todo.md`，不阻塞主线。
- V2 想法写入 `docs/backlog/v2-ideas.md`，不进入 V1。
- 不允许为了通过测试写死当前基金代码、截图数据或临时假数据。
- 不允许把当前 live 数据伪造成历史数据。
- 不允许输出买入、卖出、仓位建议或收益承诺。
- 不允许自动交易，不接券商。
- 不允许擅自修改主评分模型。
- 不允许擅自修改主风险逻辑。
- 不允许改变 daily 默认 provider 代码逻辑。
- 不允许把 observation / experiment 输出变成 production conclusion。
- 每个 Milestone 都必须更新 README / CHANGELOG / roadmap 状态。
- 每个 Milestone 通过后提交 git commit。
- 每个 Milestone 输出验收报告。

## 阻塞规则

### P0: 必须立即修复，不能进入下一个 Milestone

- 项目无法运行。
- pytest 失败。
- compileall 失败。
- daily ops 失败。
- dashboard 完全打不开。
- 数据写入失败。
- JSON contract 破坏。
- 主评分/主风险被误改。
- 出现买卖建议或收益承诺。

### P1: 当前 Milestone 内必须修复

- 当前 Milestone 必做功能缺失。
- 当前 Milestone CLI 不可用。
- 当前 Milestone dashboard 页面不可用。
- 当前 Milestone 关键输出文件缺失。
- 当前 Milestone 文档缺失。
- 当前 Milestone 验收项未通过。

### P2: 不阻塞主线

- 页面样式优化。
- 更多图表。
- 更多字段。
- 更多筛选项。
- 更多主题规则。
- 报告措辞优化。
- 交互体验增强。

## M1: Fund Detail 通用化收尾

### 目标

让 Fund Detail / Watchlist Detail 适配任意 watchlist，而不是只适配当前 3 只基金。

### 必做任务

- Fund Detail 不写死 `021511` / `021580` / `011452`。
- `watchlist-detail` 能读取任意 `configs/watchlist.yaml`。
- 主题识别规则通用化。
- `unknown` 必须输出 `unknown_reason`。
- `data_coverage` 必须可用。
- peer comparison v1 必须可用。
- `dashboard/funds.html` 必须展示 coverage / theme / peer / warnings。
- 单基金页必须展示基础信息、主题、收益窗口、数据覆盖、同主题对比、missing fields、warnings。
- `ops-status` / `latest_summary` 必须展示 fund detail coverage 状态。
- README / CHANGELOG / roadmap 状态必须更新。

### 验收标准

- 换一批 watchlist 不改代码仍可运行。
- `unknown` 有 `unknown_reason`。
- peer sample 不足时不失败。
- `dashboard/funds.html` 可打开。
- 不修改主 score / risk_issues。
- 不输出买卖建议。

### 不做什么

- 不做 historical backfill。
- 不做 portfolio analysis。
- 不做 news evidence。
- 不做 Web Console。
- 不接主评分。
- 不接主风险。
- 不输出买卖建议。

### 产物路径

- `outputs/fund_details/fund_detail_{code}.json`
- `outputs/fund_details/fund_detail_{code}.md`
- `outputs/fund_details/watchlist_fund_details.json`
- `outputs/fund_details/watchlist_fund_details.md`
- `outputs/dashboard/funds.html`
- `outputs/dashboard/funds/{code}.html`
- `outputs/ops_status.json`
- `outputs/latest_summary.md`

### CLI 命令

```bash
python -m fund_agent.cli fund-detail --code 021511 --output-dir outputs
python -m fund_agent.cli watchlist-detail --watchlist-file configs/watchlist.yaml --output-dir outputs
python -m fund_agent.cli generate-evidence-dashboard --runs-dir outputs/runs --review-state outputs/manual_review_state.json --output-dir outputs/dashboard --days 30
python -m fund_agent.cli ops-status --output-dir outputs --json-output outputs/ops_status.json --write-latest-summary
```

### 测试要求

- 任意 watchlist 读取测试。
- `unknown_reason` 测试。
- `data_coverage` 测试。
- peer comparison sample 不足测试。
- dashboard funds 页面测试。
- ops-status / latest_summary coverage 测试。

### 是否允许修改主评分/主风险

不允许。

### 是否允许输出买卖建议

不允许。

## M2: Historical Backfill 历史回填层

### 目标

用真实历史数据补齐趋势样本，避免只能等待未来 daily run。

### 必做任务

- 新增 `historical-backfill` CLI。
- 支持 fund NAV 历史回填。
- 支持 market snapshot 历史回填。
- 明确 `run_type=historical_backfill`。
- `live_daily` 和 `historical_backfill` 必须严格区分。
- backfill 输出不能污染 live daily evidence。
- dashboard / trend / fund detail 可以读取 backfill 数据，但必须显示 backfill 标记。
- 不允许用今天 live 数据伪造过去日期。
- README / CHANGELOG / roadmap 状态必须更新。

### 验收标准

- backfill 输出包含 `run_type=historical_backfill`。
- live run 和 backfill run 可区分。
- market trend 能读取 backfill snapshot。
- fund detail 能利用历史 NAV。
- 不伪造历史。
- 不输出买卖建议。

### 不做什么

- 不做主评分接入。
- 不做主风险接入。
- 不做新闻舆情。
- 不做自动交易。

### 产物路径

- `outputs/runs/YYYY-MM-DD/`
- `outputs/backfill/backfill_report.json`
- `outputs/backfill/backfill_summary.md`
- `outputs/market/snapshots/YYYY-MM-DD.json`

### CLI 命令

```bash
python -m fund_agent.cli historical-backfill --start-date 2026-06-01 --end-date 2026-06-30 --provider fixture --output-dir outputs
python -m fund_agent.cli market-trend --market-dir outputs/market --output-dir outputs
python -m fund_agent.cli fund-detail --code 021511 --output-dir outputs
```

### 测试要求

- 日期范围解析测试。
- `run_type=historical_backfill` 测试。
- live/backfill 严格区分测试。
- 不覆盖 live evidence 测试。
- market trend 读取 backfill snapshot 测试。
- fund detail 读取 historical NAV 测试。

### 是否允许修改主评分/主风险

不允许。

### 是否允许输出买卖建议

不允许。

## M3: Portfolio Analysis 组合分析层

### 目标

从单基金观察升级到组合观察。

### 必做任务

- 读取 `configs/portfolio.yaml`。
- 支持持仓金额 / 份额 / 成本 / 权重。
- 计算主题暴露。
- 计算基金类型暴露。
- 计算主动基金 / ETF / ETF 联接 / QDII / 债券 / 货币等分布。
- 计算集中度。
- 识别主题重复和重叠风险。
- 输出 `portfolio_report.json` / `portfolio_report.md`。
- dashboard 新增 `portfolio.html`。
- `ops-status` / `latest_summary` 增加 portfolio 状态。
- README / CHANGELOG / roadmap 状态必须更新。

### 验收标准

- `portfolio.yaml` 为空时不失败，提示未配置持仓。
- 配置持仓时可生成组合分析。
- `dashboard/portfolio.html` 可打开。
- 输出只包含观察和风险提示，不包含交易建议。

### 不做什么

- 不做自动调仓。
- 不做买卖建议。
- 不接券商。
- 不自动交易。
- 不修改主评分/主风险。

### 产物路径

- `outputs/portfolio/portfolio_report.json`
- `outputs/portfolio/portfolio_report.md`
- `outputs/dashboard/portfolio.html`
- `outputs/runs/YYYY-MM-DD/portfolio_report.json`

### CLI 命令

```bash
python -m fund_agent.cli portfolio-analysis --portfolio-config configs/portfolio.yaml --output-dir outputs
```

### 测试要求

- 空 portfolio 测试。
- 持仓金额/份额/成本/权重解析测试。
- 主题暴露聚合测试。
- 类型暴露聚合测试。
- 集中度和重叠风险测试。
- dashboard/ops/latest summary 测试。

### 是否允许修改主评分/主风险

不允许。

### 是否允许输出买卖建议

不允许。

## M4: News / Announcement Evidence 新闻公告证据层

### 目标

为市场主题和自选基金补充新闻、公告、基金公告、研报摘要等证据。

### 必做任务

- 新增 `news_evidence` 模块。
- 接入至少一种稳定来源，来源不可用时可用 mock/fixture。
- 记录 `title` / `source` / `published_at` / `url` / `related_themes` / `related_funds` / `evidence_strength`。
- 做去重。
- 做时间戳对齐。
- 做来源质量标记。
- 输出 `news_evidence_report.json` / `news_evidence_summary.md`。
- dashboard 新增 `news.html`。
- 证据必须有来源和时间。
- 无法验证来源时必须标记 `low_confidence`。
- README / CHANGELOG / roadmap 状态必须更新。

### 验收标准

- 新闻证据能关联主题或基金。
- 证据有来源和时间。
- `low_confidence` 会明确标注。
- `dashboard/news.html` 可打开。
- 不输出买卖建议。

### 不做什么

- 不做新闻直接驱动主评分。
- 不做舆情交易信号。
- 不输出买卖建议。
- 不大量抓取不稳定网页。
- 不违反数据源使用规则。

### 产物路径

- `outputs/news/news_evidence_report.json`
- `outputs/news/news_evidence_summary.md`
- `outputs/dashboard/news.html`
- `outputs/runs/YYYY-MM-DD/news_evidence_report.json`

### CLI 命令

```bash
python -m fund_agent.cli collect-news-evidence --output-dir outputs
```

### 测试要求

- fixture 新闻源测试。
- 来源字段完整性测试。
- 去重测试。
- 时间戳对齐测试。
- low confidence 测试。
- dashboard/news 页面测试。

### 是否允许修改主评分/主风险

不允许。

### 是否允许输出买卖建议

不允许。

## M5: Web Console v1

### 目标

从静态 HTML 升级为本地可操作工作台，不需要用户每天手敲命令。

### 必做任务

- FastAPI 或 Streamlit 二选一，选择更简单稳定的方案。
- 本地启动命令。
- 首页展示 ops status。
- 页面入口：Market / Funds / Portfolio / News / Review / Reports。
- 支持一键运行 daily ops。
- 支持一键刷新 dashboard。
- 支持查看 latest summary。
- 支持查看 manual review queue。
- 支持更新 manual review state。
- 支持查看 fund detail。
- 支持查看 portfolio report。
- 支持查看 news evidence。
- README / CHANGELOG / roadmap 状态必须更新。

### 验收标准

- 本地服务可启动。
- 页面可打开。
- 一键 daily ops 可触发。
- manual review state 可更新。
- 不影响原 CLI。
- 不输出买卖建议。

### 不做什么

- 不做公网部署。
- 不做多用户。
- 不做登录权限。
- 不做 SaaS。
- 不做自动交易。
- 不接主评分/主风险。
- 不接 LLM/Agent/MCP。

### 产物路径

- `fund_agent/web_console.py` 或等价入口。
- `outputs/dashboard/index.html`
- `outputs/dashboard/market.html`
- `outputs/dashboard/funds.html`
- `outputs/dashboard/portfolio.html`
- `outputs/dashboard/news.html`
- `outputs/dashboard/review.html`

### CLI 命令

```bash
python -m fund_agent.cli web-console --output-dir outputs
```

### 测试要求

- 本地服务启动测试。
- 页面入口测试。
- daily ops 触发测试。
- dashboard refresh 测试。
- manual review state 更新测试。
- 原 CLI 回归测试。

### 是否允许修改主评分/主风险

不允许。

### 是否允许输出买卖建议

不允许。

## M6: V1 Release 收口

### 目标

把系统整理成可以长期自用的 V1.0.0。

### 必做任务

- README 重写成正式使用手册。
- 安装步骤完整。
- 配置说明完整。
- watchlist / portfolio / providers / themes 配置说明完整。
- daily / weekly scheduler 说明完整。
- Web Console 启动说明完整。
- outputs 目录说明完整。
- dashboard 说明完整。
- backfill 说明完整。
- news evidence 说明完整。
- portfolio 说明完整。
- 风险边界说明完整。
- CHANGELOG 完整。
- 打 tag `v1.0.0`。
- 给出 V1 验收报告。

### 验收标准

- 新环境按 README 能安装。
- 能配置 watchlist。
- 能配置 portfolio。
- 能手动跑 daily。
- 能安装 scheduler。
- 能打开 Web Console。
- 能查看 Market / Funds / Portfolio / News / Review。
- 能生成日报周报。
- pytest / compileall 通过。
- `v1.0.0` tag 存在。

### 不做什么

- 不做 V2 功能。
- 不做 Agent/Skill/MCP。
- 不做自动交易。
- 不做券商接入。
- 不做 SaaS。
- 不做移动端。

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
- daily/weekly ops smoke。
- Web Console smoke。
- scheduler install/status/uninstall 文档核对。

### 是否允许修改主评分/主风险

默认不允许。只有单独批准的主模型变更任务才允许。

### 是否允许输出买卖建议

不允许。

## 每个 Milestone 通用验证命令

```bash
python -m pytest -q
python -m compileall -q fund_agent
```

如果涉及 daily ops：

```bash
PROVIDER=fixture OUTPUT_DIR=outputs AS_OF=2026-06-23 ENABLE_MARKET_INTELLIGENCE=true scripts/run_daily_ops.sh
```

如果涉及 dashboard：

```bash
python -m fund_agent.cli generate-evidence-dashboard --runs-dir outputs/runs --review-state outputs/manual_review_state.json --output-dir outputs/dashboard --days 30
```

如果涉及 ops-status：

```bash
python -m fund_agent.cli ops-status --output-dir outputs --json-output outputs/ops_status.json --write-latest-summary
```

## 每个 Milestone 验收报告

每个 Milestone 完成后必须输出：

1. 当前 Milestone 名称。
2. 实现摘要。
3. 必做项完成情况。
4. 不做项是否遵守。
5. 自验结果。
6. pytest / compileall 结果。
7. 相关 CLI 验证结果。
8. dashboard / report 路径。
9. 是否修改主评分/主风险，必须回答。
10. 是否输出买卖建议，必须回答。
11. 是否进入下一个 Milestone，必须回答。
12. 如果进入下一个 Milestone，说明进入原因。
13. 如果不能进入，列出 P0/P1 问题。
14. P2 Todo 写入 `docs/backlog/v1-todo.md`。
15. 当前 git commit / branch / push 状态。

## 自动推进规则

- M1 自验通过后，自动进入 M2。
- M2 自验通过后，自动进入 M3。
- M3 自验通过后，自动进入 M4。
- M4 自验通过后，自动进入 M5。
- M5 自验通过后，自动进入 M6。
- M6 自验通过后，停止，输出 V1 Release Report。
- 任何 Milestone 出现 P0/P1，停止自动推进，只修当前 Milestone。
- 任何需求不明确，先采用保守实现；如涉及外部服务密钥、付费接口、交易、主评分/主风险变更，必须停止并输出 `needs human decision`。
- 不允许因为 P2 优化项阻塞主线。
- 不允许自动进入 V2。

## 当前定位

M1 Fund Detail 通用化收尾和 M2 Historical Backfill 历史回填层均已完成并自验通过。当前项目进入 M3 Portfolio Analysis 组合分析层。
