# V3 M2 Fund Profile Data 本地验收

日期：2026-08-12

结论：M2 代码、离线回归、真实 AKShare 数据、contract 和产品浏览器门禁通过，可形成本地 `3.0.0a2` 候选。远端 PR、CI、push 和 `v3.0.0-alpha.2` annotated tag 未获本轮授权，因此尚未对外发布，也不进入 M3 实现。

## 用户可见结果

- 基金终端使用三类 AKShare 目录的规范化并集，真实快照包含 27,487 只基金；代码、名称、类型、场内标记、申购状态、排序和分页均在服务端执行。
- 目录独有代码可直接进入稳定 `/funds/:code` 路由，不需要写入旧 `fund_details`。
- 详情页提供“概览 / 净值与业绩 / 费率与规则”标签，展示公司、托管人、经理、成立日、份额规模、业绩基准、跟踪标的、申购赎回规则和可用费率。
- 普通产品 API/DOM 不展示 provider、cache、endpoint、schema、metadata、raw warning 或绝对路径。

## P0 边界证据

- 新资料只写 `fund_catalog_*`、`fund_purchase_*`、`fund_profiles`、`fund_trading_rules`、`fund_fees`；旧 `fund_basics` / `fund_details` schema 与 round-trip 回归通过。
- 全量 `fund_name_em`、`fund_open_fund_rank_em`、`fund_etf_spot_em`、`fund_purchase_em` 只由显式 `refresh-fund-profile-reference` 调用。
- 三只完整单基金 trace 的 endpoint 仅为 `fund_overview_em` / `fund_fee_em`；详情 service、API 和浏览器均未调用全量 endpoint。
- daily 默认 Provider、watchlist、portfolio、scheduler、主评分和主风险均未修改；artifact 固定 `main_score_changed=false`、`main_risk_changed=false`。

## 真实参考快照

显式刷新命令成功退出：

```bash
python -m fund_agent.cli refresh-fund-profile-reference \
  --provider akshare --cache-file data/cache/funds.sqlite \
  --provider-config configs/providers.yaml --output-dir outputs \
  --as-of 2026-08-12
```

- catalog：49,162 个 raw rows，27,487 个规范化去重 entry，snapshot 成功切换。
- purchase：27,181 个 raw rows，27,181 个映射 rule，snapshot 成功切换。
- 报告边界字段确认旧表、daily scheduler、主评分、主风险均未改变。

## 三类 mandatory live smoke

使用只保留 reference snapshot、删除 code-scoped profile/rule/fee 的隔离临时 SQLite 逐只执行，避免 fresh cache 命中伪装成 live：

| code | 代表类型 | artifact | fee rows | live/mapped/skipped | critical warning |
| --- | --- | --- | ---: | ---: | ---: |
| `021511` | 开放式混合基金 | profile/trading/fee 均 `updated` | 6 | 11 / 10 / 3 | 0 |
| `021580` | ETF 联接基金 | profile/trading/fee 均 `updated` | 5 | 10 / 9 / 3 | 0 |
| `510300` | 场内 ETF | profile/trading/fee 均 `updated` | 2 | 9 / 4 / 6 | 0 |

每个 trace 都同时包含 `fund_profile`、`fund_trading_rule`、`fund_fees` operation。三个 artifact 均通过 `validate-contract --fund-profile`。

AKShare `1.18.64` 的当前上游标题与旧“申购费率（前端）”indicator 不一致，三类 trace 分别保留 1、1、2 个非 critical `live_fetch_error` warning；ETF 同时没有赎回费率表。实现没有删除 warning，也没有绕过 AKShare 直接抓取或伪造数据。可验证的赎回费率、管理费率、托管费率和销售服务费率按原始文本展示，固定金额不会被转换为百分比。

## 离线与产品验收

- Python：`593 passed, 1 skipped`；`python -m compileall -q fund_agent` 通过。
- Web：14 个测试文件、46 个测试通过；TypeScript typecheck 与 production build 通过。
- Fund Profile contract：三只真实 artifact 均通过。
- 真实浏览器：1440 / 768 / 375 的 M2 详情布局通过；目录/申购筛选追加在 1280 / 375 验证，页面级 `scrollWidth == clientWidth`，console 0 error/0 warning。
- 可访问性：tablist/tab/tabpanel、方向键/Home/End、active `tabindex`、控件可访问名称、44px 移动控件和非颜色唯一表达通过。
- 真实交互：`021511 + 开放申购` 精确返回 1 条，详情跳转保留 `return_to` 查询；费率页展示 6 条真实行。

## 剩余门禁与回滚

- 待用户明确授权后才能执行远端 push、PR、CI 和 annotated tag；在此之前不写成“alpha.2 已发布”。
- M3 ETF Market Workspace 尚未开始，不得把 M2 的场内交易状态当成 ETF 盘口、订单或交易能力。
- 回滚到 `v3.0.0-alpha.1` 时只切换代码并重新部署 Product Web；不得删除 SQLite、`outputs/`、用户配置或 scheduler 来掩盖外部数据问题。
