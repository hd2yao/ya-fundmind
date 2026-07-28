# V3 M1 行业板块历史可用性 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让同一 AKShare provider 内可获得的行业板块日线在东方财富历史端点不可用时仍可通过精确名称的同花顺行业日线补齐，并在用户页面保持自然语言空态与真实数据边界。

**Architecture:** 现有 `AkshareProvider.fetch_industry_history` 仍优先使用 `stock_board_industry_hist_em`，以保持 BK 代码和既有缓存语义。仅当该端点失败或没有有效行时，才调用 AKShare 暴露的 `stock_board_industry_index_ths`；该回退只允许 EastMoney 行业名称与 THS 行业名称完全一致，禁止模糊映射或用近似板块伪造同一条曲线。`MarketSectorService` 继续只缓存成功规范化的数据；Product API 继续隐藏 provider、cache、endpoint 与原始异常。

**Tech Stack:** Python 3.10+、AKShare、SQLite `FundCache`、FastAPI Product API、React/Vite、pytest、Vitest。

---

## 背景与根因

2026-07-28 的独立 live smoke 证明：行业目录可读取，但 `stock_board_industry_hist_em(BK1607)` 在当前网络环境返回 `Expecting value: line 1 column 1 (char 0)`；直接访问其 EastMoney HTTP/HTTPS 历史端点分别返回 `502` / 连接关闭。根因不是前端固定选择了旧板块，也不是将空数据误渲染成曲线。

同一环境中，AKShare 的 `stock_board_industry_name_ths` 与 `stock_board_industry_index_ths` 可用。例如，精确名称 `医药商业`、`半导体`、`白酒` 可以返回 1,210 个日频点；`医药流通` 不属于 THS 行业名称集合，必须保持“暂未取得连续日线”，不能替换为近似板块。

## 执行契约

- 默认 pytest/Vitest 不访问真实网络；全部 provider 行为使用 fake AKShare module。
- 仅使用 AKShare SDK 已暴露的 endpoint；不新增第二个 provider，也不把 THS 与 EastMoney 不同名称混为同一行业。
- `stock_board_industry_hist_em` 始终优先；THS 仅为 endpoint fallback，trace/warning 在诊断层可见，普通 Product API 不显示 implementation details。
- 只在成功返回有日期和收盘价的点时写入现有 `market_series` cache；异常、空行、名称不匹配绝不写入伪造点。
- 不修改主评分、主风险、daily 默认 provider、watchlist、portfolio、scheduler 时间或交易边界。
- `v3.0.0-alpha.1` 的 live smoke 仍须获得至少一个可复核的成功行业历史 trace；本计划不能以 mock 或旧 cache 代替该门禁。

## Task 1: Provider endpoint fallback

**Files:**
- Modify: `fund_agent/providers.py`
- Test: `tests/test_akshare_sector_provider.py`

**Step 1: Write the failing test**

为 fake AKShare module 增加一个失败的 `stock_board_industry_hist_em` 和一个返回 THS 列（`日期`、`开盘价`、`收盘价`、`最高价`、`最低价`、`成交量`、`成交额`）的 `stock_board_industry_index_ths`。断言：

```python
points = provider.fetch_industry_history(
    "BK1042", name="医药商业", start_date="20260721", end_date="20260722"
)

assert [point.date for point in points] == ["2026-07-21", "2026-07-22"]
assert provider.last_health.endpoints[1].endpoint == "stock_board_industry_index_ths"
assert any(warning.code == "endpoint_fallback" for warning in provider.last_health.warnings)
```

另加“名称不在 THS 目录时仍抛出 `ProviderUnavailable`、不写缓存”的测试，防止近似匹配。

**Step 2: Run test to verify it fails**

Run: `python -m pytest -q tests/test_akshare_sector_provider.py -k ths`

Expected: FAIL，因为当前实现只尝试 EastMoney 行业历史 endpoint。

**Step 3: Write minimal implementation**

- 为 `AkshareProvider.fetch_industry_history` 提取单端点映射逻辑。
- EastMoney 调用失败或映射后无有效点时，使用传入的 `name` 调用 `stock_board_industry_index_ths`。
- 新增 THS 行业日线 mapper，仅接受精确名称 endpoint 返回的数据；不请求或维护跨市场名称映射表。
- 汇总 endpoint trace、rows、warnings；将 `endpoint_fallback` 设为 warning，而整个 provider 仅在两个 endpoint 都不可用时标记 critical。
- 成功点保持已有 `series_kind=market_industry_history`、`source=akshare`、TTL 与 SQLite upsert 语义。

**Step 4: Run test to verify it passes**

Run: `python -m pytest -q tests/test_akshare_sector_provider.py -k ths`

Expected: PASS.

**Step 5: Commit**

```bash
git add fund_agent/providers.py tests/test_akshare_sector_provider.py
git commit -m "fix: add AKShare industry history endpoint fallback"
```

## Task 2: Explicit sector-history refresh and cache coverage

**Files:**
- Modify: `fund_agent/sector_history.py`
- Modify: `fund_agent/cli.py`
- Test: `tests/test_sector_history.py`
- Create: `tests/test_market_sector_history_refresh_cli.py`

**Step 1: Write the failing tests**

先定义一个只接受显式 `BK` symbols 的 `refresh_sector_histories` 批量方法，以及 CLI：

```bash
python -m fund_agent.cli refresh-market-sector-history \
  --provider akshare --symbols BK1042,BK1036 --output-dir outputs
```

测试必须证明：一条板块失败不阻断另一条，成功/回退/不可用计数和每个 symbol 的状态写入 `outputs/market/sector_history_refresh_report.json`；fixture provider 返回 exit `2`；空或非法 symbols 返回清晰的 CLI 参数错误。

**Step 2: Run tests to verify they fail**

Run: `python -m pytest -q tests/test_sector_history.py tests/test_market_sector_history_refresh_cli.py`

Expected: FAIL，因为批量刷新 API/CLI 尚不存在。

**Step 3: Write minimal implementation**

- `MarketSectorService.refresh_sector_histories(symbols, now, as_of)` 逐个调用已存在的 `get_sector_history(..., window="all", force_refresh=True)` 语义（为 sector method 添加该可选参数），不让单项失败终止批处理。
- 复用当前 catalog、cache、fallback 和 history horizon 逻辑；报告仅供诊断/运维，不进入主 report、score 或 risk。
- CLI 仅支持 `--provider akshare`，解析去重后的 `BKdddd` 列表，写结构化 JSON，并在无成功或缓存回退时返回 `2`。
- 不把该命令加入 daily scheduler；用户点击板块时的现有按需读取仍保留，运维可用此命令主动预热明确关注的板块。

**Step 4: Run tests to verify they pass**

Run: `python -m pytest -q tests/test_sector_history.py tests/test_market_sector_history_refresh_cli.py`

Expected: PASS.

**Step 5: Commit**

```bash
git add fund_agent/sector_history.py fund_agent/cli.py tests/test_sector_history.py tests/test_market_sector_history_refresh_cli.py
git commit -m "feat: add explicit industry history refresh"
```

## Task 3: Product user-state and browser regression

**Files:**
- Modify: `fund_agent/product_views.py` only if the new refresh/status payload needs safe projection
- Modify: `web/src/pages/MarketPage.tsx`
- Test: `tests/test_web_api.py`
- Test: `web/src/pages/MarketPage.test.tsx`

**Step 1: Write failing UI/API tests**

增加真实 Product API unavailable response 的断言：只包含自然语言“暂未取得连续日线”，不出现 `AKShare`、`cache`、`endpoint`、`fallback`、`normal`、`warning`、`degraded` 或原始错误。MarketPage 测试应断言选中无日线行业仍保留其当日行情，但右侧明确说明“该板块暂未取得可连续展示的历史行情”，而不是渲染空图或无意义的诊断区域。

**Step 2: Run tests to verify they fail**

Run: `cd web && npm test -- --run src/pages/MarketPage.test.tsx` and `python -m pytest -q tests/test_web_api.py`

Expected: 只有在文案或空态不符合新断言时 FAIL。

**Step 3: Write minimal implementation**

- 将 Product sector-history missing state 映射为简洁的用户层标题/说明；保持 data date/status 的自然语言字段。
- 页面空态不显示原始 unavailable reason、provider/cache 名称或工程枚举；保留已选择的板块当前行情，且明确历史日线不可用。
- 不新增“查看走势”右缘动作，不恢复重复 modal，不改变用户可直接点击行的选择交互。

**Step 4: Run tests to verify they pass**

Run: `python -m pytest -q tests/test_web_api.py && cd web && npm test -- --run src/pages/MarketPage.test.tsx`

Expected: PASS.

**Step 5: Commit**

```bash
git add fund_agent/product_views.py web/src/pages/MarketPage.tsx tests/test_web_api.py web/src/pages/MarketPage.test.tsx
git commit -m "fix: clarify unavailable industry history in product view"
```

## Task 4: Evidence, live smoke and release decision

**Files:**
- Modify: `docs/backlog/v3-todo.md`
- Modify: `specs/v3-fund-information-platform/tasks.md`
- Create: `docs/reviews/2026-07-28-v3-m1-sector-history-readiness.md`

**Step 1: Run verification**

```bash
python -m pytest -q
python -m compileall -q fund_agent
cd web && npm test -- --run && npm run typecheck && npm run build
python -m fund_agent.cli refresh-market-sector-history --provider akshare --symbols BK1042,BK1036 --output-dir /tmp/ya-fundmind-sector-smoke
python -m fund_agent.cli product-web --output-dir outputs
```

**Step 2: Record actual live evidence**

- 真实 smoke 成功：记录 symbols、point counts、`outputs/market/sector_history_refresh_report.json`、对应 trace/health 与数据日期；再进行 M1 alpha release 计划。
- 真实 smoke 失败：记录 endpoint、时间、错误分类和 cache 结果；标注为 alpha blocker，不创建 tag，不把 mock/cache 说成 live 成功。

**Step 3: Browser and accessibility verification**

在 1440、768、375 三个 viewport 验证 Market 页面，无页面级水平溢出、表格可操作、空态自然语言可读、所有组合状态不泄露内部字段；运行基础 accessibility 检查。

**Step 4: Converge documentation**

- 将完成项和仍受上游可用性限制的项同步到 `tasks.md`、backlog 和 review。
- 仅 P0/P1 清零且核心 live trace 成功后，恢复 `v3.0.0-alpha.1` release worktree；否则保持 alpha release pending。
