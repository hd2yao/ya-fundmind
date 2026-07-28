# V3 Fund Information Platform Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把 v2.6 的研究底座升级为本地基金/ETF 信息平台，并通过六个有限 Milestone 发布 `v3.0.0`。

**Architecture:** 保留现有 provider/cache/artifact/Research Copilot，新增独立 Fund Profile、ETF Quote 和产品 view model。所有 provider 原始数据先标准化和缓存，再由 Product Web API 返回用户模型；工程诊断进入独立系统面。

**Tech Stack:** Python 3.10+、dataclass、SQLite、AKShare、React、TypeScript、Vite、pytest、Vitest、Playwright。

---

任务完成状态只在 `specs/v3-fund-information-platform/tasks.md` 维护。本计划描述执行顺序，不重复维护完成状态。

## 执行入口

- 产品评审：`docs/reviews/2026-07-28-v2.6-product-reassessment.md`
- 开源复盘：`docs/research/2026-07-28-fund-platform-open-source-refresh.md`
- 架构：`docs/architecture/v3-fund-information-platform.md`
- Design Lock：`docs/design/v3-fund-information-platform-design-lock.md`
- Roadmap：`docs/roadmap/v3-delivery-roadmap.md`
- Spec/Tasks/Contract：`specs/v3-fund-information-platform/`

## Task 1：M1 数据真实性

**Files:**

- Modify: `fund_agent/providers.py`
- Modify: `fund_agent/portfolio_analysis.py`
- Test: `tests/test_provider.py`
- Test: `tests/test_portfolio_analysis.py`

**Steps:**

1. 写失败测试：新 V3 provider/domain observation 的缺失收益保持 `None`。
2. 运行 focused test，确认当前 product path 已丢失 missing 语义。
3. 最小实现 optional V3 observation 和 product adapter。
4. 新增 legacy adapter，并用 v2.6 fixture snapshot 证明 `FundRecord`、主 score/risk 不变。
5. 写失败测试：组合缺失当前估值不生成 0 和 -100%。
6. 最小修改组合汇总和 view model。
7. 运行相关 pytest 和 compileall。
8. focused diff review 并提交。

## Task 2：M1 产品视图与导航

**Files:**

- Create: `fund_agent/product_views.py`
- Modify: `fund_agent/web_api.py`
- Modify: `web/src/App.tsx`
- Modify: `web/src/layout/AppShell.tsx`
- Modify: `web/src/pages/MarketPage.tsx`
- Create: `web/src/pages/WatchlistPage.tsx`
- Modify: `web/src/pages/PortfolioPage.tsx`
- Modify: `web/src/pages/NewsPage.tsx`
- Test: corresponding Python/React tests

**Steps:**

1. 为用户 view model 与 diagnostics 分离写失败 API 测试。
2. 实现最小 product view adapter。
3. 为一级导航和自选路由写失败 React 测试。
4. 保持根路由进入 `/market`，将 `MarketPage` 收敛为产品入口，并实现市场/基金/自选/组合一级导航；`OverviewPage` 继续只服务 `/status`。
5. 将 Research/Reports/System 移到二级。
6. 把 raw warning code 映射为中文文案。
7. fixture 新闻默认隐藏或明确 demo。
8. 运行 Python/React focused tests。
9. Playwright 验收 1440/768/375 和 a11y。
10. 提交、PR、CI、merge、`alpha.1`。

## Task 3：M2 Fund Profile

**Files:**

- Create: `fund_agent/fund_profile.py`
- Modify: `fund_agent/models.py`
- Modify: `fund_agent/providers.py`
- Modify: `fund_agent/cache.py`
- Modify: `fund_agent/web_api.py`
- Modify: `fund_agent/cli.py`
- Modify: `web/src/pages/FundDetailPage.tsx`
- Create: `docs/contracts/fund-profile-v1.md`
- Test: provider/cache/API/CLI/Web tests

**Steps:**

1. 先冻结 contract 和 model tests。
2. 分 endpoint 为 overview、purchase、fee 写 mapping 失败测试。
3. 逐个实现 mapper，每个 endpoint 单独 commit。
4. 写 cache migration/upsert/load/TTL/stale 测试并实现。
5. 写 profile service/API/CLI 测试并实现。
6. 写概览、净值与业绩、费率与规则 UI 测试并实现。
7. 运行三种基金真实 live smoke；未成功不得发布 `alpha.2`。
8. 全量门、PR、CI、merge、`alpha.2`。

## Task 4：M3 ETF Market

按 `specs/v3-fund-information-platform/tasks.md` 的 `T301`–`T307` 执行。每个 endpoint、cache、API、UI 独立 RED/GREEN/commit。ETF 类型检查必须早于字段渲染，普通基金和 LOF 测试必须证明没有误用 ETF 盘口字段；历史必须保存并展示 `adjust`。

## Task 5：M4 Deep Fund Detail

按 `T401`–`T407` 执行。持仓数据的复合键必须包含报告期；任何“最新持仓”文案必须同时显示披露日期。经理、评级和风险收益字段不得写入主 score/risk。

## Task 6：M5 Product & OSS Hardening

按 `T501`–`T506` 执行。重点验证：

- 自选和持仓边界。
- 空配置和示例配置。
- 普通页面无内部 code、本机路径和 fixture 冒充。
- clean clone/install。
- 默认 loopback 和隐私。

## Task 7：M6 Release

按 `T601`–`T606` 执行。Final 必须使用 clean main、真实版本、全量测试、可选 live 真实结果、scheduler 状态、三视口截图和回滚证据。失败 smoke 不得伪造。

## 每个 Milestone 的最小命令

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q fund_agent
npm --prefix web test
npm --prefix web run typecheck
npm --prefix web run build
.venv/bin/python -m fund_agent.cli validate-contract --output-dir outputs
```

真实 AKShare smoke、Product Web 和 Playwright 命令在各 Milestone 开始时根据实际 CLI/API 冻结，不在规划阶段虚构。
