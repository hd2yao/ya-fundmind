# V3 Fund Information Platform 技术方案

## 推荐方案

在 v2.6 上新增“产品视图模型 + 基金资料领域服务”，复用现有 provider、cache、artifact 和 Product Web，不重写全项目。

```text
AKShare
-> endpoint-specific mapper
-> canonical domain model
-> SQLite cache
-> product service
-> API view model
-> React page

provider health / raw warning
-> diagnostics service
-> system page
```

## 为什么不直接扩展 FundRecord

`FundRecord` 当前同时承担筛选、报告、估值和 Web 目录用途。继续向其中塞入费率、持仓、评级、盘口等字段会造成：

- ETF 和开放式基金字段混杂。
- 主评分意外读取新字段。
- cache 和 contract 难以演进。
- 前端继续消费工程模型。

V3 新增独立模型，现有 `FundRecord` 只保持兼容。

缺失值采用三层语义：

1. 新 V3 provider/domain observation 使用 optional 值。
2. V3 product view/JSON 将缺失序列化为 `null`。
3. legacy `FundRecord` 和旧报告只通过显式 compatibility adapter 保持 v2.6 输入；主评分/主风险用 snapshot regression 证明不变。

## 预计模块

### M1

- Create: `fund_agent/product_views.py`
- Modify: `fund_agent/providers.py`
- Modify: `fund_agent/portfolio_analysis.py`
- Modify: `fund_agent/web_api.py`
- Modify: `web/src/App.tsx`
- Modify: `web/src/layout/AppShell.tsx`
- Modify: `web/src/pages/MarketPage.tsx`
- Create: `web/src/pages/WatchlistPage.tsx`
- Modify: existing page copy and diagnostics rendering

### M2

- Create: `fund_agent/fund_profile.py`
- Modify: `fund_agent/models.py`
- Modify: `fund_agent/providers.py`
- Modify: `fund_agent/cache.py`
- Modify: `fund_agent/web_api.py`
- Modify: `web/src/pages/FundDetailPage.tsx`
- Create: `docs/contracts/fund-profile-v1.md`

### M3

- Create: `fund_agent/etf_market.py`
- Modify: models/provider/cache/API
- Modify: `web/src/pages/MarketPage.tsx`
- Modify: `web/src/pages/FundDetailPage.tsx`
- Create: `docs/contracts/etf-quote-v1.md`

### M4

- Create: `fund_agent/fund_holdings.py`
- Create: `fund_agent/fund_reference.py`
- Modify: models/provider/cache/API/detail UI

### M5

- Modify: watchlist/portfolio/system pages
- Modify: README/installer/ops/privacy docs
- Add: clean-install and open-source safety tests

### M6

- Update: version, CHANGELOG, README, roadmap, backlog, tasks
- Create: migration and release report
- Add/update: compatibility, E2E, performance and security gates

## 数据库策略

- 新表优先于向旧表追加大量可空列。
- 每个实体带 `source/as_of/updated_at/expires_at/metadata`。
- 规模保存资产/份额维度；费率保存类型、条件、渠道、原费率和优惠费率；评级按机构保存。
- 复合键包含 code、报告期或日期。
- migration 只 `CREATE TABLE IF NOT EXISTS` / additive column。
- stale fallback 不覆盖原始 source，产品 view model另行表达。

## API 策略

- `/api/funds` 保持兼容。
- 新增 `/api/funds/{code}/profile` 等独立资源。
- ETF 资源只对 exchange-traded code 返回。
- 用户响应和 diagnostics 响应分离；两者都使用稳定枚举/code，用户响应可附 `display_message`。
- 所有列表服务端分页、排序、筛选。

## Web 策略

- 复用现有 React/Vite，不引入新的 UI 框架。
- 复用 DataTable、chart 和 resource hooks，但调整信息架构。
- Web 使用 translation map 将稳定 code 本地化。
- 只在系统页加载 diagnostics。
- 每个页面有 loading/empty/error/stale/partial 状态。

## 测试策略

- mapping：真实形状 fixture + 变体/缺列/坏行。
- cache：migration、upsert/load、TTL、stale fallback。
- domain：ETF/普通基金类型边界。
- API：contract、分页、错误、diagnostics 隔离。
- Web：行为优先，不断言实现细节。
- 浏览器：1440/768/375、关键交互、console、横向溢出、a11y。
- 回归：pytest、compileall、React test/typecheck/build、contract、CLI、scheduler。
- 发布：默认 CI 离线；每个新增核心 endpoint 在对应 alpha/beta/Final 前必须完成代表性真实 smoke 和 trace。

## 风险与回滚

| 风险 | 控制 |
| --- | --- |
| AKShare 字段变化 | endpoint mapper、mock 变体、trace、fail-soft |
| 请求过多 | 按需 profile、TTL、批量 endpoint 与单只 endpoint 分开 |
| schema 膨胀 | 独立领域模型和 contract |
| 新 UI 破坏旧 API | adapter/view model，保留现有 endpoint |
| 数据误导 | missing 保持 null，产品文案与诊断分离 |
| 开源隐私 | fixture 默认、gitignore、安全测试 |

每个 Milestone 可回退到前一 tag；不删除 SQLite、outputs 或用户配置。
