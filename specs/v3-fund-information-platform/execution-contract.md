# V3 Fund Information Platform 执行契约

## Intent Lock

本次大版本只解决：把 v2.6 的研究与数据底座升级为完整、诚实、可浏览的本地基金/ETF 信息平台，并发布 `v3.0.0`。

## Scope Fence

### 范围内

- 基金目录、档案、净值、ETF 行情、持仓、费率、经理、评级。
- 市场、基金、自选、组合的产品化 Web。
- 用户 view model 与 diagnostics 分层。
- cache、trace、contract、scheduler 和开源交付。

### 范围外

- 主评分、主风险和自动推荐。
- 买卖建议、交易、券商和账户。
- 真实新闻/公告 provider、多源核验。
- SaaS、多用户、账号、公网部署、移动端和小程序。

## Approved Behavior

### 必须满足

- V3 domain/view 中 unknown 保持 unknown；legacy `FundRecord` 只经 compatibility adapter 保持 v2.6 行为。
- ETF 与开放式基金使用不同语义。
- 用户层不暴露内部诊断。
- 事实来自结构化 API/JSON。
- v2.6 自动化和研究能力兼容。

### 明确不改变

- daily 默认 provider。
- M1-M4 不修改 watchlist 和 portfolio 配置内容；M5 只可在备份并保留现有本地文件的前提下设计 example/local 配置迁移。
- 主评分算法和主风险规则。
- 现有 v2.6 contract 字段语义。
- scheduler 时间。

## Design Constraints

- 核心 domain service 不依赖 CLI 或 React。
- provider 原始字段只能进入 mapper。
- 全量 endpoint 只能由 TTL snapshot job 刷新，单基金详情不得逐基金触发全量 endpoint。
- M2 的 catalog、purchase status 和 profile 必须写入独立新表；禁止写入或改变旧 `fund_basics` / `fund_details` 的语义。
- M2 全量 snapshot 通过完整性与映射阈值后才能原子切换 active snapshot；失败批次不得覆盖上一份可用快照。
- 新公共 JSON 有 schema、validator 和兼容测试。
- 默认测试无网络；对应 Milestone 的核心 AKShare endpoint 在发布前必须有真实 smoke 和 trace，失败阻断该版本发布。
- API 列表服务端分页。
- Web 默认 loopback。
- 不删除用户 SQLite、outputs 或配置。

## Review Gates

### 实现前

- 当前 Milestone 的 AC 已映射到 task/test。
- 外部 AKShare endpoint 已用官方文档核对。
- 当前 P0/P1 为空。
- UI 变更先更新 Design Lock。

### 实现中

- RED -> GREEN -> focused diff -> commit。
- endpoint mapper 覆盖缺列、空值、坏行和字段变体。
- M2 每个回滚单元都验证旧表 round-trip、详情请求全量 endpoint 零调用，以及 legacy daily/score/risk 回归。
- 连续两个页面重复转换逻辑时回到 product view model。
- 范围、schema、权限或版本变化时先更新契约。

### 实现后

- fresh verification。
- 对抗式检查数据真实性、类型边界和 debug 泄露。
- PR + CI + merge。
- clean main 运行验收和 tag。

## Rewind Triggers

### 回到 spec

- 目标变为推荐、交易、券商、实时推送或公网 SaaS。
- 新闻/公告变成 V3 发布 blocker。

### 回到 plan

- AKShare 接口无法满足关键字段。
- 需要破坏性数据库迁移或新强制依赖。
- 需要网页写入 watchlist/portfolio。

### 暂停

- 需要付费授权数据或 secret 才能完成核心路径。
- 需要删除用户历史。
- 发现 secret/持仓/本机路径将进入开源提交。
- 同一 gate 连续三次修复失败。

## Test Obligations

- Python unit/integration、compileall。
- React test/typecheck/build。
- contract compatibility。
- CLI/API E2E。
- 1440/768/375 Playwright、console、overflow、a11y。
- 对应 Milestone 的 mandatory AKShare live smoke 和 trace。
- v2.6 fixture/live 主评分与主风险 snapshot regression。
- daily/weekly/Product Web scheduler。
- clean install 和 upgrade/rollback。

## Git / Release

- 分支使用 `codex/` 前缀。
- 每个 Milestone 独立 PR。
- CI 未通过不合并。
- P0/P1 未清零不打 tag。
- 不 force-push。
- 不提交 outputs、cache、logs、`.venv`、用户配置副本或 secret。

任务状态唯一真源为 `specs/v3-fund-information-platform/tasks.md`；Roadmap 只定义 Milestone gate，Implementation Plan 只定义执行方式。
