# V3 M2 Fund Profile Data Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不修改主评分、主风险和 daily 默认路径的前提下，为已索引基金提供 AKShare 概况、交易规则和费率资料，并将其安全展示在详情页。

**Architecture:** 使用独立 `FundCatalogEntry` / `FundProfile` domain 与 SQLite 新表，保留既有 `FundDetailView`、`FundRecord` 和历史净值服务。全量目录/申购状态由显式 TTL snapshot 写入独立表并原子切换；按 code 的概况和费率 cache-first、可 live 补全。产品 API 只投影用户字段，trace/diagnostics 保留完整新鲜度与 warning。

**Tech Stack:** Python 3.10+、AKShare、SQLite、FastAPI、React/Vite、pytest、Vitest、Playwright。

---

## Intent Lock

- 本次只交付 V3 M2 Fund Profile Data 和 `v3.0.0-alpha.2` 发布门。
- 不修改主评分、主风险、默认 Provider、watchlist、portfolio、daily/weekly scheduler、交易边界或新闻能力。
- 不把 `fund_purchase_em` 放进详情页按需调用；不引入新 UI framework 或外部 Provider。
- 不向 `fund_basics` 写目录/申购状态，不向 legacy `fund_details` 写 Profile；新表与旧 daily fallback、Tiantian cache 完全隔离。

## P0 设计门禁

1. **旧缓存隔离**：目录、申购状态和 profile 只进入新表。任何写入 `fund_basics` / `fund_details` 的实现均视为 P0，并立即停止当前批次。
2. **请求拓扑隔离**：`fund_purchase_em` 与目录全量 endpoint 只允许显式预热命令调用；详情 service、Product API 和页面请求调用它们均视为 P0。
3. **legacy contract 隔离**：旧 `FundDetailView`、详情 artifact、daily/weekly 和 score/risk 输入必须逐项兼容；通过新资料字段改变旧 round-trip 均视为 P0。

门禁证据必须包含：刷新前后旧表 schema/row round-trip 对比、详情请求 Provider spy 的全量 endpoint 零调用、v2.6 daily 与 score/risk snapshot 回归。

## 实现前 Analyze

- `fund_agent/fund_detail.py` 与 `fund_agent/fund_history.py` 已能提供研究补充字段和 NAV；M2 必须叠加而不是替换。
- `AkshareProvider.fetch_funds()` 已使用 rank/ETF endpoint；M2 将 `fund_name_em` 作为目录覆盖补充，并以独立 catalog snapshot 避免改动 daily 行为。
- `FundCache` 已支持 metadata、TTL 和 `fund_details`；M2 新建 profile/rule/fee 表，避免给 legacy table 堆大量空字段。
- `fund_purchase_em` 一次可返回大规模全量数据，只能由显式预热命令写入 `fund_purchase_snapshots` / `fund_purchase_statuses`；详情页和产品 API 只能读取该 snapshot。
- `web_api.py` 现有 `/api/product/funds/{code}` 保持兼容；M2 新增 `/profile` 子资源和前端懒加载 tab。
- `/profile` 必须避免被动态详情路由吞掉；产品详情存在性同时接受 M1 market index 与 M2 catalog index。
- 真实 AKShare 端点可能有列名或可用性变动；mock tests 固定字段语义，三类 real smoke 才是 alpha.2 发布依据。

## Task 1: Freeze contract, models, and release state

**Files:**
- Create: `specs/v3-fund-information-platform/m2-fund-profile-spec.md`
- Create: `docs/contracts/fund-profile-v1.md`
- Modify: `docs/roadmap/v3-delivery-roadmap.md`
- Modify: `docs/backlog/v3-todo.md`
- Modify: `specs/v3-fund-information-platform/tasks.md`
- Modify: `README.md`, `docs/README.md`, `docs/releases/v3.0.0-alpha.1-release-report.md`
- Test: `tests/test_version.py`

**Step 1:** Write the M2 contract and record `v3.0.0-alpha.1` tag/commit evidence.

**Step 2:** Verify docs do not state an untagged release and M2 non-goals do not include scoring, risk, scheduler or configuration changes.

**Step 3:** Commit `docs: start v3 m2 fund profile delivery`.

## Task 2: Add pure Fund Profile model and row mappers

**Files:**
- Modify: `fund_agent/models.py`
- Modify: `fund_agent/providers.py`
- Create: `tests/test_akshare_fund_profile_provider.py`

**Step 1: Write failing tests** for overview aliases, empty/malformed rows, fee values that are fixed amounts, fee channel, and six-digit code normalization.

**Step 2: Run** `python -m pytest -q tests/test_akshare_fund_profile_provider.py`; expected failure because the profile API/mappers do not exist.

**Step 3: Implement minimum dataclasses and pure mappers.** Keep source/newness metadata explicit, retain fee strings, and classify invalid rows as skipped warnings.

**Step 4: Run the focused test**; expected pass. Do not call real network.

**Step 5: Commit** `feat: add fund profile data models`.

## Task 3: Add cache schema and Profile Service

**Files:**
- Modify: `fund_agent/cache.py`
- Create: `fund_agent/fund_profile.py`
- Create: `tests/test_fund_profile_cache.py`
- Create: `tests/test_fund_profile_service.py`

**Step 1: Write failing tests** for additive migration, legacy table isolation, atomic active-snapshot switch, fresh cache hit without provider call, live write, stale fallback and empty cache failure.

**Step 2: Run focused tests**; expected failure because profile cache/service are absent.

**Step 3: Implement** `fund_catalog_snapshots` / `fund_catalog_entries`、`fund_purchase_snapshots` / `fund_purchase_statuses`、`fund_profiles`、`fund_trading_rules`、`fund_fees` tables and a cache-first bundle service. Full snapshots commit only after mapping-threshold validation and active-snapshot switch. The service may live-fetch overview/fees per code; it may only read purchase status from the all-fund snapshot.

**Step 4: Run focused tests**; expected pass.

**Step 5: Commit** `feat: cache fund profile data`.

## Task 4: Add controlled provider operations, CLI, artifact, and trace

**Files:**
- Modify: `fund_agent/providers.py`
- Modify: `fund_agent/cli.py`
- Modify: `fund_agent/trace.py`, `fund_agent/contract.py`
- Create: `tests/test_fund_profile_cli.py`
- Create: `tests/test_fund_profile_contract.py`

**Step 1: Write failing tests** for `fetch-fund-profile`, explicit catalog/purchase refresh, atomic snapshot activation, trace endpoint counters, artifact validation, no live network in default tests, and a proof that profile/detail calls never invoke `fund_purchase_em`.

**Step 2: Run focused tests**; expected failure because commands and artifact validator are absent.

**Step 3: Implement minimum commands:** `fetch-fund-profile --code` and explicit reference refresh. Each writes only designated output/cache/trace paths, preserves retention prefix isolation, and never changes daily scheduling.

**Step 4: Run focused tests**; expected pass.

**Step 5: Commit** `feat: add fund profile operations`.

## Task 5: Add Product API and detail-page tabs

**Files:**
- Modify: `fund_agent/web_api.py`, `fund_agent/product_views.py`
- Modify: `web/src/api/types.ts`, `web/src/api/client.ts`
- Modify: `web/src/pages/FundDetailPage.tsx`, `web/src/styles/global.css`
- Modify: `tests/test_web_api.py`
- Create/Modify: `web/src/pages/FundDetailPage.test.tsx`

**Step 1: Write failing API and Web tests** for route matching, a profile subresource, user-safe component-level partial status, catalog-only code lookup, and tab selection/lazy fee loading.

**Step 2: Run focused Python/Vitest tests**; expected failure because the endpoint/types/tabs do not exist.

**Step 3: Implement the smallest compatible API and UI.** Keep existing history route and detail response intact. Use Chinese labels; no cache/provider/raw diagnostics in product payload or screen.

**Step 4: Run focused tests**; expected pass.

**Step 5: Commit** `feat: show fund profile tabs`.

## Task 6: Acceptance, release, and convergence

**Files:**
- Create: `docs/reviews/2026-07-28-v3-m2-fund-profile-acceptance.md`
- Create: `docs/releases/v3.0.0-alpha.2-release-report.md`
- Modify: `README.md`, `CHANGELOG.md`, `docs/README.md`, `docs/roadmap/v3-delivery-roadmap.md`, `docs/backlog/v3-todo.md`, `specs/v3-fund-information-platform/tasks.md`, `pyproject.toml`, `fund_agent/__init__.py`, `tests/test_version.py`

**Step 1:** Run full Python/Web/contract/fixture CLI verification, then real AKShare smoke for mixed fund `021511`, ETF-link `021580`, and ETF `510300` if all endpoints respond.

**Step 2:** Run real-browser 1440/768/375 and accessibility checks. Verify no horizontal overflow, tabs are keyboard-accessible, and user pages do not show internal diagnostics.

**Step 3:** Perform spec + code review, create PR, wait CI, merge only with P0/P1 resolved, tag `v3.0.0-alpha.2` on clean main.

**Step 4:** Add converge notes: each AC, remaining external endpoint limitations and rollback to `v3.0.0-alpha.1` without deleting outputs/cache/scheduler.

## Test Obligations

- Focused pytest follows RED/GREEN for every new public function and error path.
- Full: `python -m pytest -q`, `python -m compileall -q fund_agent`, `npm test -- --run`, `npm run typecheck`, `npm run build`.
- Product Web: `python -m fund_agent.cli product-web --dry-run`, strict contract validation, demo/daily fixture regression, browser 1440/768/375 and accessibility check.
- Network: live smoke is optional during development and mandatory only for alpha.2 release; default pytest/CI never accesses it.

## Risks and Rollback

- AKShare field/API drift: map aliases, preserve unknown source fields only in diagnostics, fail closed for profile fields.
- All-fund endpoint cost: no detail page call may invoke catalog/purchase snapshot; explicit refresh commands have trace and retry bounds.
- Bad cache migration：只允许 additive `CREATE TABLE IF NOT EXISTS`；既有 `fund_basics`、`fund_details`、`fund_navs` 保持不变。目录和申购状态全量 snapshot 只有验证通过后才能原子激活。
- UI leakage: product projection tests recursively reject provider/cache/endpoint/metadata fields.
- Rollback: switch to `v3.0.0-alpha.1`, redeploy only static Product Web; never delete `outputs/`, SQLite or scheduler to mask a data issue.

## Rewind Triggers

- If installed AKShare does not expose a required endpoint or its live result contradicts the field semantics, update spec/contract before coding around it.
- If profile data needs a new provider, scheduler change, score/risk input, or config write, stop M2 and return to product scope review.
- If a cache migration cannot be additive or a product response requires raw diagnostics, stop and redesign the boundary.
