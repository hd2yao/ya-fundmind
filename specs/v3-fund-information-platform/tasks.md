# V3 Fund Information Platform 任务清单

## Batch 0：评审与冻结

- [x] `T001` 审计 v2.6 代码、产物、scheduler 和 Product Web。
  映射：全部 AC 的基线。
- [x] `T002` 更新开源项目与 AKShare 能力调研。
- [x] `T003` 起草 V3 架构、Design Lock、Roadmap、Spec 和执行契约。
- [x] `T004` 完成对抗式评审并修复规划 P1。
- [x] `T005` 完成本地验证并具备 PR 条件；规划 PR 合并后 V3 契约生效。

## Batch 1：M1 Product Truth & IA

- [x] `T101` 为 V3 optional observation / product `null` 添加失败测试。
  映射：`AC-001`、`AC-004`
- [x] `T102` 新增 V3 product mapper 和 legacy `FundRecord` adapter，并锁定 v2.6 score/risk snapshot。
- [x] `T103` 为组合 unknown valuation 添加失败测试。
  映射：`AC-002`
- [x] `T104` 修复组合汇总和页面 unknown 语义。
- [x] `T105` 新增产品 view model 与 diagnostics 分层。
  映射：`AC-003`、`AC-008`、`AC-009`
- [x] `T106` 重组导航和首页。
  映射：`AC-005` 至 `AC-007`
- [x] `T107` 新增只读自选页。
  映射：`AC-023`
- [x] `T108` 隐藏正式 fixture 新闻入口。
  映射：`AC-026`
- [x] `T109` 完成 Web 三视口、a11y 和全量回归。
- [x] `T110` 增加 fixture 新闻、Research/Evidence、daily/weekly 和 `main_score_changed=false/main_risk_changed=false` 回归。
- [x] `T111` 行业板块历史 endpoint 回退、显式预热、cache 覆盖、用户空态与真实 smoke。
  映射：`AC-020`、`AC-021`
- [ ] `T112` 完成 M1 PR、CI、clean `main` 验收和 `v3.0.0-alpha.1`。

## Batch 2：M2 Fund Profile

- [ ] `T201` 冻结 Fund Profile contract 和模型。
  映射：`AC-012` 至 `AC-014`
- [ ] `T202` 定义 AKShare 基金库并集、去重/份额规则和 endpoint coverage report。
- [ ] `T203` 接入基金目录/概况 mapper，稳定详情 URL。
- [ ] `T204` 按“全量 TTL snapshot / 单基金按需”接入申购赎回和费率，保留条件、渠道和原/优惠费率。
- [ ] `T205` 新增 cache migration、TTL 和 stale fallback。
- [ ] `T206` 新增 profile service/API/CLI 和申购状态筛选。
- [ ] `T207` 新增概览、净值与业绩、费率与规则 UI。
- [ ] `T208` 完成三类基金 mandatory live smoke、trace、回归、PR 和 `alpha.2`。

## Batch 3：M3 ETF Market

- [ ] `T301` 冻结 ETF Quote contract 和类型边界。
  映射：`AC-018`、`AC-019`、`AC-022`
- [ ] `T302` 扩展 ETF spot mapper，并证明普通基金/LOF 不进入 ETF quote。
- [ ] `T303` 接入 ETF 历史，保存和展示 `adjust`。
- [ ] `T304` 接入主要指数 spot。
- [ ] `T305` 新增 cache/service/API。
- [ ] `T306` 新增 ETF 市场工作区和详情标签页。
- [ ] `T307` 完成 ETF/指数 mandatory live smoke、trace、回归、PR 和 `beta.1`。

## Batch 4：M4 Deep Fund Detail

- [ ] `T401` 接入股票/债券持仓和资产配置。
  映射：`AC-017`
- [ ] `T402` 接入基金经理和基金公司资料。
- [ ] `T403` 接入评级和风险收益分析。
- [ ] `T404` 接入分红/拆分历史。
- [ ] `T405` 新增 report-period-aware cache/service/API。
- [ ] `T406` 完整详情标签页和披露滞后说明。
- [ ] `T407` 完成回归、PR 和 `beta.2`。

## Batch 5：M5 Product & OSS Hardening

- [ ] `T501` 完成自选筛选/分组/空态。
- [ ] `T502` 完成组合数据真实性和配置状态。
  映射：`AC-024`
- [ ] `T503` 完成系统诊断页和普通页面清理。
- [ ] `T504` 完成 README、首次运行、数据来源、隐私和免责声明。
- [ ] `T505` 设计 example/local config 迁移，先备份且不删除当前 watchlist/portfolio。
- [ ] `T506` 完成 clean clone/install、redaction 和开源安全测试。
  映射：`AC-030`、`AC-031`
- [ ] `T507` 完成 RC 全量验收、PR 和 `v3.0.0-rc.1`。

## Batch 6：M6 V3 Release

- [ ] `T601` 完成 v2.6/V3 compatibility matrix。
  映射：`AC-027`
- [ ] `T602` 完成 migration/rollback。
- [ ] `T603` 完成 Python/React/contract/CLI/API/Web/scheduler E2E。
- [ ] `T604` 完成所有核心 endpoint mandatory live smoke、trace、性能、安全、三视口和 accessibility。
  映射：`AC-028` 至 `AC-030`
- [ ] `T605` 完成 legacy score/risk snapshot、Research/Evidence、fixture 和 provider compatibility matrix。
- [ ] `T606` 完成版本、CHANGELOG、文档和 release report。
- [ ] `T607` clean main post-release ops check，发布 `v3.0.0`。
  映射：全部 AC

## 完整 AC / Task / Test 映射

| AC | Task | 必须测试 |
| --- | --- | --- |
| `AC-001` | `T101`、`T102` | optional mapping、JSON null、legacy adapter snapshot |
| `AC-002` | `T103`、`T104` | unknown valuation 不产生 0/-100% |
| `AC-003` | `T105` | product field provenance |
| `AC-004` | `T101`、`T108` | fixture/live/stale/fallback 状态 |
| `AC-005` | `T106` | 一级导航路由 |
| `AC-006` | `T106` | 二级导航路由 |
| `AC-007` | `T106` | 根路由和 MarketPage 首屏 |
| `AC-008` | `T105`、`T109` | raw code/path/trace 不在普通 DOM |
| `AC-009` | `T105` | stable code + Web translation |
| `AC-010` | `T202`、`T206` | 并集、搜索、筛选、排序、分页 |
| `AC-011` | `T203` | 稳定详情 URL |
| `AC-012` | `T201`、`T203`、`T204` | profile 字段和费率语义 |
| `AC-013` | `T204`、`T205` | batch TTL / on-demand / partial |
| `AC-014` | `T205` | 字段级 provenance diagnostics |
| `AC-015` | `T207` | NAV/累计净值/窗口 |
| `AC-016` | `T207` | 短样本/缺点/日期 |
| `AC-017` | `T401`–`T406` | report period 和样本 |
| `AC-018` | `T301`–`T303` | ETF quote/history/adjust |
| `AC-019` | `T302` | 普通基金/LOF 无 ETF 盘口 |
| `AC-020` | `T304`–`T306` | 指数快照/历史/板块 |
| `AC-021` | `T305`、`T307` | live/fallback/date |
| `AC-022` | `T301`、`T306` | API/DOM 无订单和下单 |
| `AC-023` | `T107`、`T501` | watchlist 来源和边界 |
| `AC-024` | `T502`、`T505` | portfolio 空/示例/真实状态 |
| `AC-025` | `T110`、`T605` | Research/Evidence/Report 回归 |
| `AC-026` | `T108`、`T503` | fixture 正式入口隔离 |
| `AC-027` | `T601`、`T603`、`T605` | v2.6 compatibility |
| `AC-028` | `T208`、`T307`、`T604` | offline CI + mandatory live trace |
| `AC-029` | `T109`、`T604` | 1440/768/375 + a11y |
| `AC-030` | `T506`、`T603` | clean install/upgrade/rollback/scheduler |
| `AC-031` | `T505`、`T506` | config migration/privacy/git safety |
| `AC-032` | `T102`、`T110`、`T605` | score/risk snapshot、无交易文本 |
| `AC-033` | `T202` | raw/mapped/dedup/skipped/type coverage |
