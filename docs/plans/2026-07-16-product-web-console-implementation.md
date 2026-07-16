# Product Web Console Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不改变 YA FundMind OS 研究计算、主评分、主风险和 daily 运行路径的前提下，新增一个可产品化交付的本地 React Web Console，并保留 Streamlit 回退入口。

**Architecture:** FastAPI app factory 将固定 `output_dir` 下的现有结构化研究产物转换为稳定的本地 JSON API；Vite + React + TypeScript 前端消费这些 API，提供八个任务页面、统一状态模型和证据钻取。Python API 与前端静态构建解耦，开发时由 Vite proxy，生产时由 FastAPI 挂载 `web/dist`。

**Tech Stack:** Python 3.10+、FastAPI、Uvicorn、React 18、TypeScript、Vite、React Router、Recharts、Lucide React、Vitest、Testing Library、Playwright。

---

## Task 1: FastAPI 可选依赖与 API 外壳

**Files:**
- Modify: `pyproject.toml`
- Create: `fund_agent/web_api.py`
- Create: `tests/test_web_api.py`

**Step 1: 写失败测试**

覆盖：

- `create_web_app(output_dir=...)` 返回 FastAPI app。
- `/api/health` 返回 `status=ready`、当前 generator、`local_only=true`。
- App state 固定保存已解析的 output dir，不接受请求参数覆盖。
- output dir 不存在时 health 返回可解释的 `missing_outputs`，服务仍可启动。

**Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest -q tests/test_web_api.py`

Expected: 因 `fund_agent.web_api` 不存在而失败。

**Step 3: 实现最小 app factory**

- 新增 `webapp` optional dependency：FastAPI + Uvicorn。
- `dev` extra 包含 API 测试依赖。
- 使用 app factory 固定 output dir 和 review state path。
- 所有响应使用 JSON，不返回本地堆栈。

**Step 4: 运行测试**

Run: `.venv/bin/python -m pytest -q tests/test_web_api.py`

Expected: PASS。

**Step 5: Commit**

```bash
git add pyproject.toml fund_agent/web_api.py tests/test_web_api.py
git commit -m "feat: add local web api shell"
```

## Task 2: 结构化只读 API 与安全边界

**Files:**
- Modify: `fund_agent/web_api.py`
- Modify: `tests/test_web_api.py`

**Step 1: 写失败测试**

覆盖：

- `/api/overview` 返回 ops、summary、review 与 data quality。
- `/api/market`、`/api/funds`、`/api/portfolio`、`/api/news` 返回固定 JSON payload。
- `/api/reports` 只返回 allowlist 文件元数据，不允许路径遍历。
- 缺失产物返回空 payload 与 `availability=missing`，不返回 500。
- API response 不包含环境变量、secret 或任意文件内容。

**Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest -q tests/test_web_api.py`

**Step 3: 实现 read models**

- 复用 `build_web_console_state` 和现有 JSON loader/service。
- 将页面 payload 包装为 `{availability, generated_at, data}`。
- 将报告路径转换为受控的 metadata 与应用内下载 URL。

**Step 4: 运行相关与现有 Web 测试**

Run: `.venv/bin/python -m pytest -q tests/test_web_api.py tests/test_web_console.py tests/test_web_console_sections.py`

**Step 5: Commit**

```bash
git add fund_agent/web_api.py tests/test_web_api.py
git commit -m "feat: expose structured research read models"
```

## Task 3: Copilot 与 Review 有界写接口

**Files:**
- Modify: `fund_agent/web_api.py`
- Modify: `tests/test_web_api.py`

**Step 1: 写失败测试**

覆盖：

- `POST /api/copilot/ask` 校验非空问题和最大长度，并返回结构化 citation。
- Copilot 拒答/证据不足保留原状态，不转成成功建议。
- `GET /api/reviews` 返回 queue、state 和 summary。
- `POST /api/reviews/{review_id}` 仅接受 allowlist status，限制 note/reviewer 长度。
- 不存在的 review id 返回明确 404，不创建任意记录。

**Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest -q tests/test_web_api.py`

**Step 3: 实现端点**

- 复用 `run_copilot_for_web`、`build_copilot_view_model` 与 review state service。
- 将异常映射为稳定 HTTP 状态和错误 code。

**Step 4: 运行测试**

Run: `.venv/bin/python -m pytest -q tests/test_web_api.py tests/test_web_copilot_state.py tests/test_v2_end_to_end.py`

**Step 5: Commit**

```bash
git add fund_agent/web_api.py tests/test_web_api.py
git commit -m "feat: add bounded copilot and review api"
```

## Task 4: Vite React TypeScript 工程基线

**Files:**
- Create: `web/package.json`
- Create: `web/package-lock.json`
- Create: `web/tsconfig.json`
- Create: `web/tsconfig.node.json`
- Create: `web/vite.config.ts`
- Create: `web/index.html`
- Create: `web/src/main.tsx`
- Create: `web/src/App.tsx`
- Create: `web/src/test/setup.ts`
- Create: `web/src/App.test.tsx`
- Modify: `.gitignore`

**Step 1: 建立失败测试**

- App 显示产品名称和研究边界说明。
- 默认路由渲染 Overview。
- 未知路由回到可恢复的 Not Found 页面。

**Step 2: 安装依赖并确认测试失败**

Run: `cd web && npm install && npm test -- --run`

**Step 3: 实现最小应用**

- 配置 Vitest + jsdom + Testing Library。
- 配置 Vite `/api` proxy 到本地 FastAPI。
- 禁止外部 CDN、analytics 和 telemetry。

**Step 4: 验证**

Run: `cd web && npm run typecheck && npm test -- --run && npm run build`

**Step 5: Commit**

```bash
git add .gitignore web
git commit -m "feat: scaffold typed product web app"
```

## Task 5: 应用外壳、设计令牌与响应式导航

**Files:**
- Create: `web/src/styles/tokens.css`
- Create: `web/src/styles/global.css`
- Create: `web/src/layout/AppShell.tsx`
- Create: `web/src/layout/AppShell.test.tsx`
- Create: `web/src/components/StatusBadge.tsx`
- Create: `web/src/components/StatePanel.tsx`
- Create: `web/src/components/Metric.tsx`
- Create: `web/src/lib/routes.tsx`
- Modify: `web/src/App.tsx`

**Step 1: 写失败测试**

- 桌面导航包含八个任务入口。
- 当前路由有 `aria-current=page`。
- 移动端菜单按钮有可访问名称并可打开/关闭。
- 全局边界说明始终可见。

**Step 2: 运行测试确认失败**

Run: `cd web && npm test -- --run src/layout/AppShell.test.tsx`

**Step 3: 实现外壳**

- 左侧 232px 导航、固定顶部状态栏、内容区。
- 使用 Lucide 图标和 tooltip。
- 添加 loading/empty/error/stale/degraded 状态组件。

**Step 4: 验证**

Run: `cd web && npm run typecheck && npm test -- --run`

**Step 5: Commit**

```bash
git add web/src
git commit -m "feat: build responsive research console shell"
```

## Task 6: API Client、Overview 与 Market

**Files:**
- Create: `web/src/api/client.ts`
- Create: `web/src/api/types.ts`
- Create: `web/src/hooks/useApiResource.ts`
- Create: `web/src/pages/OverviewPage.tsx`
- Create: `web/src/pages/OverviewPage.test.tsx`
- Create: `web/src/pages/MarketPage.tsx`
- Create: `web/src/pages/MarketPage.test.tsx`
- Create: `web/src/components/EvidenceDrawer.tsx`
- Create: `web/src/components/TrendChart.tsx`

**Step 1: 写失败测试**

- Overview 显示最新运行、provider、数据质量、待复核和 latest summary。
- stale/fallback/degraded 使用正确 severity。
- Market 显示主题/板块、趋势表和证据抽屉。
- 缺失数据时显示生成命令，不制造趋势。

**Step 2: 运行测试确认失败**

Run: `cd web && npm test -- --run src/pages/OverviewPage.test.tsx src/pages/MarketPage.test.tsx`

**Step 3: 实现页面**

- 使用统一 API resource hook。
- Recharts 只展示已有历史数据，不在浏览器计算评分或风险。

**Step 4: 验证**

Run: `cd web && npm run typecheck && npm test -- --run`

**Step 5: Commit**

```bash
git add web/src
git commit -m "feat: add overview and market workspaces"
```

## Task 7: Watchlist、Portfolio 与 News

**Files:**
- Create: `web/src/pages/FundsPage.tsx`
- Create: `web/src/pages/FundsPage.test.tsx`
- Create: `web/src/pages/PortfolioPage.tsx`
- Create: `web/src/pages/PortfolioPage.test.tsx`
- Create: `web/src/pages/NewsPage.tsx`
- Create: `web/src/pages/NewsPage.test.tsx`
- Create: `web/src/components/DataTable.tsx`
- Create: `web/src/components/FilterBar.tsx`

**Step 1: 写失败测试**

- Funds 标题明确为“自选研究”，支持代码/名称筛选和详情抽屉。
- Portfolio 显示暴露、集中度、观察性风险和缺口，不显示交易动作。
- News 支持主题、基金、来源筛选并保留时间与 source。
- 字段缺失不产生正向 badge 或推荐语。

**Step 2: 运行测试确认失败**

Run: `cd web && npm test -- --run src/pages/FundsPage.test.tsx src/pages/PortfolioPage.test.tsx src/pages/NewsPage.test.tsx`

**Step 3: 实现页面**

- 稳定表格几何和窄屏滚动。
- 将证据详情统一接入 EvidenceDrawer。

**Step 4: 验证**

Run: `cd web && npm run typecheck && npm test -- --run`

**Step 5: Commit**

```bash
git add web/src
git commit -m "feat: add watchlist portfolio and news workspaces"
```

## Task 8: Copilot、Review 与 Reports

**Files:**
- Create: `web/src/pages/CopilotPage.tsx`
- Create: `web/src/pages/CopilotPage.test.tsx`
- Create: `web/src/pages/ReviewPage.tsx`
- Create: `web/src/pages/ReviewPage.test.tsx`
- Create: `web/src/pages/ReportsPage.tsx`
- Create: `web/src/pages/ReportsPage.test.tsx`

**Step 1: 写失败测试**

- Copilot 提交问题并展示 finding、citation、confidence、data gap 与拒答。
- Review 只允许定义的状态变更，提交失败保留输入。
- Reports 只展示 API allowlist 返回的产物。
- 三个页面都显示“研究辅助，不改变主评分/主风险”。

**Step 2: 运行测试确认失败**

Run: `cd web && npm test -- --run src/pages/CopilotPage.test.tsx src/pages/ReviewPage.test.tsx src/pages/ReportsPage.test.tsx`

**Step 3: 实现页面**

**Step 4: 验证**

Run: `cd web && npm run typecheck && npm test -- --run`

**Step 5: Commit**

```bash
git add web/src
git commit -m "feat: add copilot review and reports workspaces"
```

## Task 9: 新 CLI、静态构建挂载与 CI

**Files:**
- Modify: `fund_agent/web_api.py`
- Modify: `fund_agent/cli.py`
- Create: `tests/test_product_web_cli.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`

**Step 1: 写失败测试**

- `product-web --dry-run` 离线验证 API 与静态 build 状态。
- `product-web --host 127.0.0.1 --port 8765` 调用 Uvicorn app factory。
- 非 loopback host 默认拒绝。
- 静态 SPA fallback 不覆盖 `/api/*`。

**Step 2: 运行测试确认失败**

Run: `.venv/bin/python -m pytest -q tests/test_product_web_cli.py tests/test_web_api.py`

**Step 3: 实现 CLI 和静态挂载**

- 保留原 `web-console` Streamlit CLI。
- 新增 `product-web`，默认 `127.0.0.1:8765`。
- CI 新增 Node job：`npm ci`、typecheck、test、build。

**Step 4: 验证**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_product_web_cli.py tests/test_web_api.py
cd web && npm ci && npm run typecheck && npm test -- --run && npm run build
```

**Step 5: Commit**

```bash
git add fund_agent tests .github/workflows/ci.yml README.md
git commit -m "feat: serve product web console locally"
```

## Task 10: 全量回归与浏览器验收

**Files:**
- Modify: `docs/plans/2026-07-16-product-web-console-design.md`
- Create: `docs/reports/2026-07-16-product-web-console-acceptance.md`

**Step 1: Python 回归**

Run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q fund_agent
```

Expected: existing tests and new API tests pass，offline。

**Step 2: 前端回归**

Run:

```bash
cd web
npm ci
npm run typecheck
npm test -- --run
npm run build
```

**Step 3: CLI E2E**

Run:

```bash
.venv/bin/python -m fund_agent.cli web-console --output-dir outputs --dry-run
.venv/bin/python -m fund_agent.cli product-web --output-dir outputs --dry-run
```

**Step 4: Playwright 视觉验收**

- 启动 `product-web` 本地服务。
- 在 375x812、768x1024、1440x1000 访问八个路由。
- 检查 body 横向溢出、文本重叠、console error、空白图表和键盘焦点。
- 保存代表性截图到 Codex visualization 目录，不提交运行时截图。

**Step 5: 写验收报告并提交**

```bash
git add docs/plans/2026-07-16-product-web-console-design.md docs/reports/2026-07-16-product-web-console-acceptance.md
git commit -m "docs: record product web console acceptance"
```

## Task 11: 分支交付但不合并 RC main

**Step 1: Focused diff review**

Run:

```bash
git diff aaf526fa6d67b6933a67b908021df9419a83c786...HEAD --check
git status --short
```

**Step 2: Push**

Run: `git push -u origin codex/v2-web-console-next`

**Step 3: 保持隔离**

- v2.0.0 Final 前不创建可合并 PR，或创建明确标记为 Draft 的 PR。
- RC readiness 达到 3/3 时切回 Final 发布优先级。
- Final 发布后更新分支基线、重新运行全量验证，再作为独立版本交付。
