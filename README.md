# YA FundMind OS

YA FundMind OS v2 是建立在稳定 V1 自动研究底座上的本地、证据驱动、只读 Research Copilot。它每天或每周自动运行，生成 Market Intelligence、Market Trend、Fund Detail、Portfolio Analysis、News Evidence、daily/weekly report 和本地 dashboard，并让 CLI、Web、Skill 与可选 MCP 通过同一套结构化证据回答研究问题。

它只做研究辅助和报告生成：不自动交易，不接券商，不输出买卖建议，不承诺收益。

## 当前状态

- 当前版本：`v2.0.0-rc.1`（Python package version：`2.0.0rc1`）
- 当前交付模式：V2 Research Copilot delivery mode
- 当前发布状态：M1-M6 RC 技术门已完成；Final 仅等待 RC 合并后的 3 个不同日期真实 scheduler run 和最终发布门。
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
- V1 -> V2 迁移：`docs/migrations/v1-to-v2.md`
- V2 排障：`docs/ops/v2-troubleshooting.md`
- 项目结构说明：`PROJECT_STRUCTURE.md`
- 文档索引：`docs/README.md`

V1 里程碑 M1 到 M6 已收口并保持稳定运行。V2 M1 到 M5 已分别通过 `v1.1.0` 至 `v1.5.0` 交付，M6 已形成 `v2.0.0-rc.1` release candidate。历史真实 run 只用于兼容验证；Final `v2.0.0` 必须由 RC main commit 在三个不同日期产生可追溯的真实 scheduler run 后才可发布。

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
  --required-git-commit "$(git rev-parse HEAD)"
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

默认地址为 `http://127.0.0.1:8765`。可先离线检查依赖和构建：

```bash
python -m fund_agent.cli product-web --output-dir outputs --dry-run
```

页面包括研究总览、市场情报、自选研究、组合分析、新闻证据、研究助手、人工审核和报告中心。服务默认只接受 loopback host，不提供公网部署；不修改主评分/主风险，不接券商，不生成交易动作。

## 风险边界

本系统输出仅用于研究辅助，不构成投资建议，不承诺收益，不包含任何自动交易指令。基金投资有风险，历史表现不代表未来收益；跨境/QDII 产品还需要额外核对汇率、时区、申赎限制和折溢价。
