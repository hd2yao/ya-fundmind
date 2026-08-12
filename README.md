# YA FundMind OS

YA FundMind OS v2 是建立在稳定 V1 自动研究底座上的本地、证据驱动、只读 Research Copilot。它每天或每周自动运行，生成 Market Intelligence、Market Trend、Fund Detail、Portfolio Analysis、News Evidence、daily/weekly report 和本地 dashboard，并让 CLI、Web、Skill 与可选 MCP 通过同一套结构化证据回答研究问题。

它只做研究辅助和报告生成：不自动交易，不接券商，不输出买卖建议，不承诺收益。

## 当前状态

- 当前稳定版本：`v2.6.0`；当前已发布预览版本：`v3.0.0-alpha.1`。
- 当前本地候选版本：`v3.0.0-alpha.2`（Python package version：`3.0.0a2`）；M2 代码、真实数据和浏览器门禁已通过，远端 PR/CI/push/tag 尚未执行。
- 当前发布状态：M1 alpha 已发布；M2 Fund Profile Data 已完成本地验收但尚未对外发布；`v2.6.0` 仍是稳定基线。
- 下一大版本定位：从“研究报告工作台”收敛为“本地基金/ETF 信息平台”，优先补齐基金档案、ETF 行情、产品信息架构和开源交付质量。
- V3 当前状态：M2 本地候选已完成，M3 尚未开始。主评分、主风险、默认 Provider 与自动化运行边界继续冻结。
- V3 产品评审：`docs/reviews/2026-07-28-v2.6-product-reassessment.md`
- V3 开源复盘：`docs/research/2026-07-28-fund-platform-open-source-refresh.md`
- V3 架构：`docs/architecture/v3-fund-information-platform.md`
- V3 Design Lock：`docs/design/v3-fund-information-platform-design-lock.md`
- V3 路线图：`docs/roadmap/v3-delivery-roadmap.md`
- V3 Todo：`docs/backlog/v3-todo.md`
- V3 Spec：`specs/v3-fund-information-platform/`
- V3 实现主计划：`docs/plans/2026-07-28-v3-fund-information-platform.md`
- V3 行业历史验收：`docs/reviews/2026-07-28-v3-m1-sector-history-readiness.md`
- V3 M1 alpha 发布报告：`docs/releases/v3.0.0-alpha.1-release-report.md`
- V3 M2 Fund Profile 规格：`specs/v3-fund-information-platform/m2-fund-profile-spec.md`
- V3 M2 Fund Profile 实现计划：`docs/plans/2026-07-28-v3-m2-fund-profile-data.md`
- V3 M2 本地验收：`docs/reviews/2026-08-12-v3-m2-fund-profile-acceptance.md`
- V3 M2 alpha.2 候选报告：`docs/releases/v3.0.0-alpha.2-release-report.md`
- V1 架构冻结：`docs/architecture/v1-system-architecture.md`
- V1 路线图：`docs/roadmap/v1-delivery-roadmap.md`
- V1 Todo：`docs/backlog/v1-todo.md`
- V2 架构：`docs/architecture/v2-system-architecture.md`
- V2 路线图：`docs/roadmap/v2-delivery-roadmap.md`
- V2 Todo：`docs/backlog/v2-todo.md`
- V2 Spec：`specs/v2-research-copilot/`
- V2 剩余想法池：`docs/backlog/v2-ideas.md`
- V1 验收报告：`docs/releases/v1.0.0-release-report.md`
- V2 RC 报告：`docs/releases/v2.0.0-rc.1-release-report.md`
- V2 Final 报告：`docs/releases/v2.0.0-release-report.md`
- V1 -> V2 迁移：`docs/migrations/v1-to-v2.md`
- V2 排障：`docs/ops/v2-troubleshooting.md`
- 项目结构说明：`PROJECT_STRUCTURE.md`
- 文档索引：`docs/README.md`

V1 里程碑 M1 到 M6 已收口并保持稳定运行。V2 M1 到 M5 已分别通过 `v1.1.0` 至 `v1.5.0` 交付，M6 先发布 `v2.0.0-rc.1`，再由同一 RC main commit 于 2026-07-15、2026-07-16、2026-07-17 产生三个可追溯的真实 scheduler run。`post_rc` 门通过后，PR #33 完成 CI 与 merge，正式 tag `v2.0.0` 指向 merge commit `f419453ec3a21592ff4cad7c542a2846b290002e`。

V2 已提供统一研究查询、证据引用、受约束 Copilot、只读 Skill/MCP 和本地 Copilot Console。自动推荐、自动交易、券商接入、SaaS、移动端和小程序不进入本次 V2 主线。

历史 Phase 计划、开源调研和旧 review 输出已归档到 `docs/archive/`，日常使用优先阅读 README、项目结构说明、contracts、ops 和 release report。

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,web]"
```

如需 AKShare live 数据：

```bash
pip install -e ".[live]"
```

如需本地只读 MCP server：

```bash
pip install -e ".[mcp]"
```

如果只想无网络验证系统，可以不安装 `live`，默认 fixture 路径仍可运行。

## 配置

- 自选池：`configs/watchlist.yaml`
- 持仓：`configs/portfolio.yaml`
- Provider、trace retention、exit policy：`configs/providers.yaml`
- 主题映射：`configs/market_themes.yaml`
- 研究循环：`configs/research_loop.yaml`
- 实验评分配置：`configs/experiment_scoring.yaml`

默认数据与样例：

- 基金 fixture：`data/fixtures/funds.json`
- 新闻证据 fixture：`data/fixtures/news_evidence.json`
- 持仓样例：`data/portfolio.example.json`
- SQLite cache：`data/cache/funds.sqlite`

## 快速运行

```bash
python -m fund_agent.cli demo --output-dir outputs --as-of 2026-06-23
python -m fund_agent.cli daily --provider fixture --watchlist-file configs/watchlist.yaml --portfolio-config configs/portfolio.yaml --output-dir outputs --as-of 2026-06-23
python -m fund_agent.cli validate-contract --output-dir outputs
```

V2 Research Copilot 只读取本地 JSON artifact，并为回答保留 finding、citation、质量等级和数据缺口：

```bash
python -m fund_agent.cli research-query --output-dir outputs --topic market
python -m fund_agent.cli build-research-evidence --output-dir outputs
python -m fund_agent.cli research-ask --output-dir outputs --question "今天市场和热门板块有什么变化？"
python -m fund_agent.cli validate-contract --output-dir outputs
```

`research-ask` 支持 market、fund、portfolio、news、history 和 quality。交易、仓位、收益承诺和买卖推荐请求会被拒绝；默认无需 LLM 或网络，不修改主评分和主风险。

## Read-only MCP / Skill

MCP 是 optional adapter，默认 stdio，只提供 `status`、`catalog`、`query`、`ask`、`evidence` 五个工具：

```bash
python -m fund_agent.cli mcp-server --output-dir outputs --dry-run
python -m fund_agent.cli mcp-server --output-dir outputs
```

Tool 不接收任意 path、URL、配置或写参数。调用 audit 写入 `outputs/audit/mcp_calls.jsonl`，question 只保留 hash 和脱敏预览。MCP 未安装时其他 CLI、daily、weekly 和 Web Console 不受影响。

仓库内手动 Research Skill：`skills/ya-fundmind-research/`。它随项目版本管理，不自动安装到全局技能目录。

核心输出：

- `outputs/fund_agent_report.md`
- `outputs/fund_agent_report.html`
- `outputs/fund_agent_report.json`
- `outputs/snapshots/YYYY-MM-DD.json`
- `outputs/traces/provider-YYYY-MM-DD.json`
- `outputs/research_queries/research_context.json`
- `outputs/evidence/research_evidence.json`
- `outputs/copilot/research_answer.json`
- `outputs/copilot/research_answer.md`
- `outputs/audit/research_queries.jsonl`
- `outputs/audit/mcp_calls.jsonl`
- `outputs/release/v2_release_readiness.json`

## V2 Release Readiness

`v2.0.0` Final 候选已经通过该门。以下命令继续用于审计历史兼容和复核 Final 证据；不得通过复制日期或修改历史 metadata 制造有效 run。

RC 前可用历史真实 run 检查兼容性，但不能用它们放行 Final：

```bash
python -m fund_agent.cli release-readiness \
  --output-dir outputs \
  --release-target v2.0.0-rc.1 \
  --observation-mode historical_compat
```

RC 合并后，Final 必须核对版本、精确 commit、干净工作树和 scheduler provenance：

```bash
python -m fund_agent.cli release-readiness \
  --output-dir outputs \
  --release-target v2.0.0 \
  --observation-mode post_rc \
  --required-app-version 2.0.0rc1 \
  --required-git-commit "$(git rev-list -n 1 v2.0.0-rc.1)"
```

门禁要求至少 3 个不同日期有效 run、strict contracts 通过、无 fallback/critical/degraded，并保持 P0/P1 为 0。完整语义见 `docs/contracts/v2-release-readiness-v1.md` 和 `docs/ops/v2-troubleshooting.md`。

## Daily / Weekly Ops

手动跑 daily ops：

```bash
PROVIDER=fixture OUTPUT_DIR=outputs ENABLE_MARKET_INTELLIGENCE=true scripts/run_daily_ops.sh
```

使用 AKShare：

```bash
PROVIDER=akshare OUTPUT_DIR=outputs ENABLE_MARKET_INTELLIGENCE=true scripts/run_daily_ops.sh
```

手动跑 weekly ops：

```bash
OUTPUT_DIR=outputs scripts/run_weekly_ops.sh
```

检查运行状态并刷新 latest summary：

```bash
python -m fund_agent.cli ops-status --output-dir outputs --json-output outputs/ops_status.json --write-latest-summary
```

## 定时任务

先 dry-run：

```bash
bash scripts/install_launchd_scheduler.sh --daily --weekly --dry-run
```

安装 daily 和 weekly：

```bash
PROVIDER=akshare ENABLE_MARKET_INTELLIGENCE=true bash scripts/install_launchd_scheduler.sh --daily --weekly
```

只安装 21:30 的 daily：

```bash
PROVIDER=akshare ENABLE_MARKET_INTELLIGENCE=true DAILY_HOUR=21 DAILY_MINUTE=30 bash scripts/install_launchd_scheduler.sh --daily
```

查看状态：

```bash
bash scripts/status_launchd_scheduler.sh
```

卸载时不会删除 `outputs`、`logs`、`runs` 或 dashboard：

```bash
bash scripts/uninstall_launchd_scheduler.sh --daily --weekly
```

更完整说明见 `docs/ops/scheduler-automation.md`。

## Web Console

启动本地 Web Console：

```bash
python -m fund_agent.cli web-console --output-dir outputs
```

启动前自检：

```bash
python -m fund_agent.cli web-console --output-dir outputs --dry-run
```

Web Console 提供：

- Ops Status
- Latest Summary
- Research Copilot 问题输入和示例问题
- finding / citation / data gap / quality 展开查看
- 最近脱敏 research audit
- Market
- Funds
- Portfolio
- News
- Review
- Reports
- 一键 daily ops
- 一键刷新 dashboard
- manual review state 更新

Web Console 读取本地 JSON contract，不从 Markdown 反向提取事实。Copilot 无需 LLM 即可运行；交易、仓位、收益承诺和买卖推荐请求会被拒绝。Console 仍只运行在本地，不做公网部署，不做多用户权限，不接主评分/主风险。

## 常用 CLI

```bash
python -m fund_agent.cli screen --watchlist-file configs/watchlist.yaml --output-dir outputs
python -m fund_agent.cli portfolio --portfolio-config configs/portfolio.yaml --output-dir outputs
python -m fund_agent.cli market-scan --provider fixture --output-dir outputs
python -m fund_agent.cli market-trend --market-dir outputs/market --output-dir outputs
python -m fund_agent.cli fund-detail --code 021511 --output-dir outputs
python -m fund_agent.cli watchlist-detail --watchlist-file configs/watchlist.yaml --output-dir outputs
python -m fund_agent.cli historical-backfill --provider fixture --start-date 2026-06-21 --end-date 2026-06-23 --output-dir outputs
python -m fund_agent.cli portfolio-analysis --portfolio-config configs/portfolio.yaml --output-dir outputs
python -m fund_agent.cli collect-news-evidence --output-dir outputs
python -m fund_agent.cli generate-evidence-dashboard --runs-dir outputs/runs --review-state outputs/manual_review_state.json --output-dir outputs/dashboard --days 30
```

V2 M1 统一只读研究查询：

```bash
python -m fund_agent.cli research-query --output-dir outputs --topic market
python -m fund_agent.cli research-query --output-dir outputs --topic fund --code 021511
python -m fund_agent.cli research-query --output-dir outputs --topic portfolio
python -m fund_agent.cli research-query --output-dir outputs --topic news
python -m fund_agent.cli research-query --output-dir outputs --topic history
python -m fund_agent.cli research-query --output-dir outputs --topic quality
```

默认输出为 `outputs/research_queries/research_context.json`。它只读取白名单 JSON artifact，不解析 Markdown/HTML，不修改 daily、watchlist、portfolio、主评分或主风险。

V2 M2 证据引用：

```bash
python -m fund_agent.cli build-research-evidence \
  --context outputs/research_queries/research_context.json \
  --output-dir outputs

python -m fund_agent.cli validate-contract \
  --evidence-bundle outputs/evidence/research_evidence.json
```

默认输出为 `outputs/evidence/research_evidence.json`。每个 finding 至少引用一个原始 artifact 和 RFC 6901 JSON Pointer；stale、fallback、warning、degraded、critical、冲突和 data gap 会显式降级。

可选 live smoke：

```bash
python -m fund_agent.cli smoke-akshare --watchlist-file configs/watchlist.yaml --portfolio-config configs/portfolio.yaml --output-dir outputs
```

Tiantian smoke 需要先配置 `TIANTIAN_API_BASE_URL`：

```bash
python -m fund_agent.cli smoke-tiantian --code 510300 --output-dir outputs
```

## Outputs 目录

- `outputs/latest_summary.md`：给人看的最新摘要。
- `outputs/ops_status.json`：运行状态 JSON。
- `outputs/dashboard/index.html`：静态 dashboard 首页。
- `outputs/dashboard/market.html`：市场观察。
- `outputs/dashboard/funds.html`：自选基金详情。
- `outputs/dashboard/portfolio.html`：组合观察。
- `outputs/dashboard/news.html`：新闻证据观察。
- `outputs/runs/YYYY-MM-DD/`：每日 run bundle。
- `outputs/market/`：市场扫描、趋势和快照。
- `outputs/fund_details/`：基金详情和自选池详情。
- `outputs/portfolio/`：组合分析报告。
- `outputs/news/`：新闻证据报告。
- `outputs/research_queries/`：V2 紧凑只读 Research Context。
- `outputs/evidence/`：V2 Evidence Bundle 和可定位引用。
- `outputs/backfill/`：历史回填报告。
- `outputs/logs/`：daily/weekly ops 日志。

## 数据与模型边界

- 主评分和主风险在 V1 中保持稳定。
- Tiantian enrichment、signal candidates、experiment scoring 都是观察/实验层。
- News Evidence 不直接驱动主评分或主风险。
- Historical Backfill 必须标记 `run_type=historical_backfill`，不能伪造成 live daily。
- 数据质量 degraded、fallback、stale cache 会进入报告和实验观察，但不会自动产生交易动作。

## 测试

```bash
python -m pytest -q
python -m compileall -q fund_agent
```

V2 release 还会验证：

```bash
python -m fund_agent.cli validate-contract --output-dir outputs
python -m fund_agent.cli web-console --output-dir outputs --dry-run
```

### 产品化本地 Web Console

原 `web-console` Streamlit 入口继续保留。新的 React + TypeScript Console 通过本地 FastAPI 启动，只读取既有 JSON contract 和 Python research service：

```bash
python -m pip install -e ".[webapp]"
cd web
npm ci
npm run build
cd ..
python -m fund_agent.cli product-web --output-dir outputs
```

默认地址为 `http://127.0.0.1:8768`。`v2.1.0` 的“基金探索”支持在 Market Intelligence 全市场产物中按代码、名称、类型、主题、ETF 和数据质量进行服务端搜索、排序与分页；“我的自选”仍只展示 `configs/watchlist.yaml`，两者都不表示推荐。

`v2.2` 的第一条数据终端链路允许点击任意搜索结果后按需读取历史净值：

- 默认展示最近 6 个月，可切换 `1 月 / 3 月 / 6 月 / 1 年 / 全部`。
- 新鲜 SQLite 历史缓存命中时不访问网络。
- 缓存缺失时调用 AKShare `fund_open_fund_info_em`，规范化后写入 `fund_navs`。
- live 失败时仅在本地存在历史缓存时回退，并明确展示 `stale / fallback / source / as_of`。
- 全市场继续只保存基础索引，不会一次性回填约两万只基金的全部历史。

该历史序列只用于浏览和研究观察，不进入主评分、主风险或推荐逻辑。完整设计和后续指数/板块里程碑见 [`docs/plans/2026-07-23-v2.2-fund-data-terminal-design.md`](docs/plans/2026-07-23-v2.2-fund-data-terminal-design.md)。

`v2.2` 的第二条数据终端链路在“市场情报”页提供主要指数历史走势：

- 支持上证指数、沪深 300、创业板指及 `1 月 / 3 月 / 6 月 / 1 年 / 全部`窗口。
- 指数 OHLCV 使用独立 SQLite `market_series`，不与基金净值混存。
- 新鲜缓存优先；缺失时按需读取 AKShare，live 失败且存在历史缓存时才显示 stale fallback。
- 当前环境下 AKShare 东方财富指数端点不可用时，会切换到同一 AKShare provider 的新浪指数端点，并保留 endpoint warning；这不是多源交叉核验。
- 页面同时显示最新收盘、日涨跌、样本、`source / as_of` 和可折叠日线数据表。

指数曲线只用于行情浏览和研究观察，不改变主评分、主风险或报告主结论。实现与验收见 [`docs/plans/2026-07-23-v2.2-m2-index-market.md`](docs/plans/2026-07-23-v2.2-m2-index-market.md) 和 [`docs/releases/v2.2.0-m2-acceptance.md`](docs/releases/v2.2.0-m2-acceptance.md)。

`v2.2` 的第三条数据终端链路在同一市场页增加行业板块目录与历史走势：

- 支持按行业名称或 `BK` 代码搜索，目录展示最新价、涨跌幅、总市值、换手率、上涨/下跌家数和领涨股票。
- 点击目录项后按需读取 `1 月 / 3 月 / 6 月 / 1 年 / 全部`历史日线；行业 OHLCV 继续写入独立 `market_series`，不与基金净值混存。
- 行业目录使用独立 SQLite `market_entities` 缓存；新鲜缓存优先，live 失败且存在缓存时才显式 stale fallback。
- 主题窗口表提供“搜索同名行业板块”入口；它只填入搜索条件，不声明研究主题与行情板块等同。
- 页面保留 `source / as_of / stale / fallback / data_quality_grade`，并明确标注“观察数据，不构成板块推荐”。

当前开发环境访问 AKShare 东方财富行业接口时发生代理连接中断，因此真实行业 smoke 如实记录为未成功；默认离线测试、cache fallback 和页面交互验收不依赖该网络。实现与验收见 [`docs/plans/2026-07-23-v2.2-m3-sector-market.md`](docs/plans/2026-07-23-v2.2-m3-sector-market.md) 和 [`docs/releases/v2.2.0-m3-acceptance.md`](docs/releases/v2.2.0-m3-acceptance.md)。

`v2.2` 的 M4 将 Product Web 收敛为本地基金数据终端：

- 根路径直接进入“行情总览”，一级工作区调整为“行情总览 / 基金终端 / 组合 / 研究证据”。
- 顶栏提供全局基金代码或名称搜索，提交后进入 `/funds?q=<query>` 并复用现有服务端全市场检索。
- 研究助手、人工审核、系统状态和报告中心保留为辅助入口，既有功能路由没有删除。
- 行情页增加主要指数、行业板块、主题窗口和趋势验证的页内导航；数据表、指标和图表改为紧凑的终端式布局。
- 375 / 768 / 1440 三视口无页面级横向溢出；provider 长错误会安全换行，不会破坏布局。

实现与验收见 [`docs/plans/2026-07-23-v2.2-m4-data-terminal-ui.md`](docs/plans/2026-07-23-v2.2-m4-data-terminal-ui.md) 和 [`docs/releases/v2.2.0-m4-acceptance.md`](docs/releases/v2.2.0-m4-acceptance.md)。

`v2.3` 在不改变数据 provider 和日常运行边界的情况下，将页面收敛为 Fund Research Desk：

- `daily ops` 在 `PROVIDER=akshare` 时预热三条既有允许指数；失败隔离，不妨碍其余研究产物。
- 页面同时展示行情交易日 `as_of`、本地同步 `updated_at`、缓存有效期 `expires_at`、来源与 stale/fallback，非交易日不再被误读为未刷新。
- 顶栏搜索、市场主图区、数据带和各工作区共享一套本地研究台布局；刷新只重新读取本地结构化 API，不触发浏览器中的隐式 provider 请求。

后续 `v2.4`–`v2.6` 的范围、验收与回滚边界见 [`docs/plans/2026-07-28-v2.3-to-v2.6-product-delivery.md`](docs/plans/2026-07-28-v2.3-to-v2.6-product-delivery.md)。

`v3.0.0-alpha.2` 候选在 M1 产品骨架上增加独立基金资料层：

- 显式运行 `refresh-fund-profile-reference` 才会刷新基金目录和全量申购状态；详情页、Product API、daily 与 scheduler 都不会调用这些全量 endpoint。
- 基金终端使用 `fund_name_em`、`fund_open_fund_rank_em`、`fund_etf_spot_em` 的规范化并集，支持代码、名称、类型、场内标记、申购状态、排序和服务端分页。
- `/funds/:code` 提供“概览 / 净值与业绩 / 费率与规则”标签；概况和费率只按代码读取，用户页面不显示 provider、cache、endpoint 或 raw warning。
- 目录、申购状态、概况、规则与费率只写 M2 独立表，不进入既有 `fund_basics` / `fund_details`。

显式预热与单只资料读取示例：

```bash
python -m fund_agent.cli refresh-fund-profile-reference \
  --provider akshare --cache-file data/cache/funds.sqlite --output-dir outputs
python -m fund_agent.cli fetch-fund-profile \
  --code 021511 --cache-file data/cache/funds.sqlite --output-dir outputs
python -m fund_agent.cli product-web \
  --output-dir outputs --cache-file data/cache/funds.sqlite
```

完整验收见 [`docs/reviews/2026-08-12-v3-m2-fund-profile-acceptance.md`](docs/reviews/2026-08-12-v3-m2-fund-profile-acceptance.md)。这些资料只用于浏览和研究核对；alpha.2 的远端 PR、CI、push 与 annotated tag 尚未执行。

`v2.4` 将已有的基金详情和净值缓存路径提升为独立本地浏览页面：

- 从全市场搜索或自选池进入 `/funds/:code`；返回链接保留基金终端的查询条件。
- 页面并列展示基础字段与历史净值的 `source / as_of / updated_at / expires_at / stale / fallback`，并保留明确的数据缺口。
- 历史净值继续支持 `1 月 / 3 月 / 6 月 / 1 年 / 全部`，只读取已有本地结构化 API，不增加页面隐式 provider 请求。

该详情仅供研究核对，不接入主评分、主风险或推荐逻辑。发布证据见 [`docs/releases/v2.4.0-release-report.md`](docs/releases/v2.4.0-release-report.md)。

`v2.5` 将已有 `portfolio` 结构化产物组织为配置持仓工作台：

- 持仓代码和名称可进入已有 `/funds/:code` 详情，并安全返回组合页。
- 主题和基金类型暴露并列呈现；仅在可靠估值可用时显示可比较权重，否则明确显示“权重待估值”。
- 当前估值缺失时，页面不展示由占位 `0` 推导出的市值、收益率或权重；观察性问题单独固定展示。

该组合工作台只读现有本地 JSON，不写入 portfolio 配置，不计算调仓，也不改变主评分或主风险。发布证据见 [`docs/releases/v2.5.0-release-report.md`](docs/releases/v2.5.0-release-report.md)。

`v2.6` 将已有新闻/公告 evidence 收敛为可核对的证据浏览器：

- 支持文本、主题、来源质量与证据强度的本地筛选，不改写 evidence JSON。
- 仅本地基金索引中存在的关联代码可进入 `/funds/:code`；索引外或无效代码保持不可点击并说明原因。
- `http/https` 来源可在安全新窗口打开；低置信度、fixture、缺 URL 和不安全 URL 显式降级，不作为正向结论。

该页面不抓取新闻、不将新闻接入主评分或主风险，也不输出买卖建议。发布证据见 [`docs/releases/v2.6.0-release-report.md`](docs/releases/v2.6.0-release-report.md)。

可先离线检查依赖和构建：

```bash
python -m fund_agent.cli product-web --output-dir outputs --dry-run
```

本地常驻运行：

```bash
bash scripts/deploy_local_product_web.sh
bash scripts/install_local_product_web.sh
bash scripts/status_local_product_web.sh
```

daily 更新 JSON 后页面会自动读取最新数据，不需要重新构建；只有代码升级时才运行 `deploy_local_product_web.sh`。卸载 Web 服务使用 `bash scripts/uninstall_local_product_web.sh`，不会修改 daily/weekly scheduler，也不会删除 outputs。

页面包括行情总览、基金终端、组合、研究证据、研究助手、人工审核、系统状态和报告中心。服务默认只接受 loopback host，不提供公网部署；不修改主评分/主风险，不接券商，不生成交易动作。完整运行手册见 [`docs/operations/local-product-web.md`](docs/operations/local-product-web.md)。

## 风险边界

本系统输出仅用于研究辅助，不构成投资建议，不承诺收益，不包含任何自动交易指令。基金投资有风险，历史表现不代表未来收益；跨境/QDII 产品还需要额外核对汇率、时区、申赎限制和折溢价。
