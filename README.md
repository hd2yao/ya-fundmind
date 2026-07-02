# YA FundMind | 基金智研系统

本项目是第一版本地基金/ETF 投研助手，范围只覆盖基金和 ETF，不做个股推荐，不接券商，不自动下单。

## V1 Delivery Mode

当前项目已进入 V1 delivery mode。后续开发不再无限追加 Phase，而是按 V1 可交付系统收敛。

V1 基准文档：

- 架构冻结：`docs/architecture/v1-system-architecture.md`
- 交付路线图：`docs/roadmap/v1-delivery-roadmap.md`
- V1 非阻塞 Todo：`docs/backlog/v1-todo.md`
- V2 想法池：`docs/backlog/v2-ideas.md`

后续任务以架构冻结文档和交付路线图为准。非阻塞优化进入 V1 Todo，不打断当前 Milestone。Agent、Skill、MCP、LLM、自动推荐、自动交易、券商接入、SaaS、移动端和小程序都放入 V2，不阻塞 V1。

当前 V1 进度：

- M1 Fund Detail 通用化收尾：已完成。
- M2 Historical Backfill 历史回填层：已完成。
- M3 Portfolio Analysis 组合分析层：已完成。
- M4 News / Announcement Evidence 新闻公告证据层：已完成。
- 下一步：M5 Web Console v1。

## 能力

- 基金/ETF 研究优先级评分：收益质量、趋势一致性、动量确认、风险调整、反追高惩罚、规模约束。
- 估值分类：场内 ETF/LOF、ETF 联接、QDII 代理、指数/NAV-only、unsupported。
- 持仓分析：当前市值、浮动收益、目标权重偏离、单只集中度、数据新鲜度。
- 报告输出：Markdown + HTML，包含证据标签、估值方式、风险提示和核对清单。
- 本地数据可靠性：SQLite 缓存、watchlist/portfolio YAML 配置、每日 snapshot 对比。
- 无密钥 demo：默认使用 `data/fixtures/funds.json` 和 `data/portfolio.example.json`。

## 快速运行

```bash
python -m fund_agent.cli demo --output-dir outputs --as-of 2026-06-22
```

输出：

- `outputs/fund_agent_report.md`
- `outputs/fund_agent_report.html`
- `outputs/snapshots/YYYY-MM-DD.json`

## 常用命令

```bash
# 只做基金/ETF 筛选
python -m fund_agent.cli screen --output-dir outputs

# 使用自选池配置筛选
python -m fund_agent.cli screen --watchlist-file configs/watchlist.yaml --output-dir outputs

# 用本地持仓文件分析组合
python -m fund_agent.cli portfolio --portfolio-file data/portfolio.example.json --output-dir outputs

# 用 YAML 持仓配置分析组合
python -m fund_agent.cli portfolio --portfolio-config configs/portfolio.yaml --output-dir outputs

# 生成单基金详情观察层
python -m fund_agent.cli fund-detail --code 021511 --output-dir outputs

# 生成自选池基金详情观察层
python -m fund_agent.cli watchlist-detail --watchlist-file configs/watchlist.yaml --output-dir outputs

# 生成历史回填观察数据，不修改主评分/主风险
python -m fund_agent.cli historical-backfill --provider fixture --start-date 2026-06-21 --end-date 2026-06-23 --output-dir outputs

# 基于 market snapshots 生成板块趋势观察
python -m fund_agent.cli market-trend --market-dir outputs/market --output-dir outputs

# 生成独立组合观察报告
python -m fund_agent.cli portfolio-analysis --portfolio-config configs/portfolio.yaml --output-dir outputs

# 收集新闻/公告证据候选
python -m fund_agent.cli collect-news-evidence --output-dir outputs

# 可选：尝试 AKShare 实时数据，需要先安装 akshare
python -m fund_agent.cli screen --source live --output-dir outputs
```

## 本地数据与配置

- SQLite 缓存默认路径：`data/cache/funds.sqlite`。缓存记录包含 `source`、`as_of`、`updated_at`、`expires_at`；live provider 失败且配置了缓存时，可以回退到缓存数据。
- 如果报告使用了过期缓存，基金记录会携带 stale 标记，后续报告会把它作为数据新鲜度风险提示。
- 自选池配置：`configs/watchlist.yaml`。
- 持仓配置：`configs/portfolio.yaml`。`demo` 仍默认使用 fixture 和 `data/portfolio.example.json`，便于无配置试运行。
- 每次成功运行都会写入 `outputs/snapshots/YYYY-MM-DD.json`；当存在上一期 snapshot 时，报告会展示评分、估值、风险和持仓风险变化。
- Fund Detail 输出包含 `unknown_reason`、`data_coverage`、`peer_comparison`，用于解释自选基金的数据覆盖、主题识别和同主题样本情况。
- Historical Backfill 输出写入 `outputs/backfill/`、`outputs/market/snapshots/` 和 `outputs/runs/YYYY-MM-DD/`，统一标记 `run_type=historical_backfill`；fixture 回填只用于管线验证，不代表真实历史数据。
- Portfolio Analysis 输出写入 `outputs/portfolio/portfolio_report.json` 和 `.md`，展示持仓、主题暴露、类型暴露、集中度和观察风险；它是独立观察层，不覆盖主评分/主风险。
- News Evidence 输出写入 `outputs/news/news_evidence_report.json` 和 `.md`，展示新闻/公告证据候选、来源、时间、关联主题/基金、置信度和低置信度标记；默认 fixture 路径不依赖真实网络，不接主评分/主风险。

## 测试

```bash
python -m pytest -q
```

## 风险边界

本系统输出仅用于研究辅助，不构成投资建议，不承诺收益，不包含任何自动交易指令。基金投资有风险，历史表现不代表未来收益；跨境/QDII 产品还需要额外核对汇率、时区、申赎限制和折溢价。
