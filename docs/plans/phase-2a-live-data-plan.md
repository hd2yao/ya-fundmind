# Phase 1.5 Acceptance and Phase 2A Live Data Plan

日期：2026-06-22

目标：在不扩大到完整 Phase 2 的前提下，验收 Phase 1 数据可靠性基础，并落地真实 AKShare 数据闭环：live 拉取、标准化、写入 SQLite cache、失败时回退 cache、生成 Markdown/HTML 报告和 snapshot。

边界：

- 不引入 Web、MCP、LLM、LangGraph。
- 不做真实交易、不输出收益承诺。
- 默认测试不依赖真实网络；AKShare 真实访问只作为可选 smoke test。
- 保持 `demo`、fixture、现有 CLI 和已有 pytest 不破坏。

## Phase 1.5 验收结论

| 验收项 | 当前状态 | 结论 | Phase 2A 补强 |
| --- | --- | --- | --- |
| SQLite cache 保存基金基础信息、净值、估值、详情表 | `FundCache` 已建 `fund_basics`、`fund_navs`、`fund_valuations`、`fund_details`，基础信息和 NAV 可写入。 | 基本满足 | live 成功后必须自动写入 cache。 |
| 每条缓存记录包含 `source`、`as_of`、`updated_at`、`expires_at` | `fund_basics` 和 `fund_navs` 已包含这些字段。 | 满足 | provider 需要给 live record 补齐 `as_of`/freshness metadata，报告要展示。 |
| live provider 失败时 fallback 到 cache | `AkshareProvider(cache=...)` 已有 fallback。 | 部分满足 | CLI live 路径还没有默认配置 cache，且缺少完整闭环测试。 |
| 过期缓存报告标记 stale data | 报告在估值 notes 中追加 stale 提示。 | 部分满足 | 报告需要集中展示每只基金的 source、as_of、stale 状态。 |
| 基金字段标准化 | 已有 `FundRecord` 和 AKShare row mapping。 | 部分满足 | 需要覆盖真实 AKShare dataframe 形态、字段缺失和异常行跳过。 |
| 自选池/持仓配置 | `configs/watchlist.yaml`、`configs/portfolio.yaml` 和 CLI 参数已实现。 | 满足 | 新 `daily` 命令默认使用配置文件。 |
| 历史 snapshot 和对比 | 每次运行写 `outputs/snapshots/YYYY-MM-DD.json`，报告可展示 delta。 | 满足 | live daily 流程要复用 snapshot。 |
| 回归测试和 demo 验证 | pytest/compileall/demo 已在 Phase 1 跑通。 | 满足 | Phase 2A 后继续跑完整验证。 |

## 当前最该落地的 5 个 P0/P1 任务

| Priority | Task | 为什么现在做 | 验收标准 |
| --- | --- | --- | --- |
| P0 | AKShare live success 写入 SQLite cache | 只有 fallback 没有 warm cache，断网时仍可能无数据可用。 | `AkshareProvider(cache=...)` live 成功后调用 `FundCache.upsert_funds()`；缓存记录含 `source=akshare`、`as_of`、`updated_at`、`expires_at`。 |
| P0 | AKShare 字段标准化和异常隔离 | 真实 dataframe 字段可能缺失、为空或带百分号。 | mock dataframe 测试覆盖代码、名称、类型、净值日期、估值日期、收益率、规模；坏行不影响其他基金。 |
| P0 | cache fallback 闭环进入 CLI | 当前 `--source live` 没有默认 cache，新的目标命令要求 `daily --provider akshare`。 | `python -m fund_agent.cli daily --provider akshare --watchlist-file configs/watchlist.yaml --portfolio-config configs/portfolio.yaml --output-dir outputs` 可运行；live 失败且 cache 有数据时仍生成报告。 |
| P1 | 报告数据新鲜度总览 | 用户需要直接看到数据来自哪里、截至哪天、是否 stale。 | Markdown/HTML 报告包含数据源表，展示 `source`、`as_of`、`updated_at`、`expires_at`、`stale`。 |
| P1 | live smoke test 路径文档化 | 默认 CI/本地测试不能被网络和 AKShare 安装状态拖垮，但需要人工验收真实数据。 | `tests/test_live_provider.py` 使用 mock；文档说明可选 smoke 命令和失败处理，不把真实网络放进默认 pytest。 |

## 实现步骤

1. 文档计划：新增本文件，作为 Phase 1.5 验收和 Phase 2A 施工边界。
2. Provider/cache：先写 mock 测试，再让 `AkshareProvider` 在 live 成功时写 cache，并增强 fallback metadata。
3. CLI：新增 `daily` 命令和 `--provider fixture|akshare`，保留旧 `demo`、`screen`、`portfolio` 和 `--source`。
4. Report：新增数据源与新鲜度表，Markdown/HTML 共用同一 Markdown 渲染结果。
5. 验证：运行 pytest、compileall、fixture demo、fixture daily；AKShare 真实 smoke test 作为可选手工命令。

## 可选 AKShare Smoke Test

默认测试不访问网络。安装 AKShare 且网络可用时，可以手工运行：

```bash
python -m fund_agent.cli daily --provider akshare --watchlist-file configs/watchlist.yaml --portfolio-config configs/portfolio.yaml --output-dir outputs
```

验收输出：

- `outputs/fund_agent_report.md`
- `outputs/fund_agent_report.html`
- `outputs/snapshots/YYYY-MM-DD.json`
- `data/cache/funds.sqlite`

如果 AKShare 不可用但 cache 中已有可用数据，命令应 fallback 到 cache 并在报告中标记 stale/fallback 信息。如果 cache 为空，命令应以非 0 状态退出并给出明确错误。
