# V3 Todo

## 规则

- `P0 blocking`：数据破坏、错误交易语义、核心主流程失败、测试/contract 失败、安全或隐私泄露。可以打断当前 Milestone。
- `P1 current milestone`：当前 Milestone 的必做能力。未完成不得进入下一 Milestone。
- `P2 later polish`：视觉、更多筛选、更多图表和非核心增强。不打断主线。
- 新想法先判断是否服务 V3 “基金信息平台”目标；否则留到 V3 之后。

## 当前状态

- 当前稳定版本：`v2.6.0`
- 当前开发状态：M1 执行中；Product API/view model、普通页面诊断隔离、一级导航、只读自选页、行业日线 endpoint 回退和显式刷新均已完成。下一步收口跨模块回归、PR 与 `alpha.1` 发布门禁。
- 当前 Milestone：M1 Product Truth & Information Architecture
- 当前 P0：无
- 当前 P1：M1 Product Truth & Information Architecture

## P0 Blocking

当前无已确认 P0。

出现以下情况立即升级为 P0：

- daily/weekly、Product Web、pytest、compileall 或 contract 无法运行。
- 缺失数据被写入 cache 为不可恢复的真实值。
- 用户配置、outputs 或历史 snapshot 被迁移删除。
- 产品新增交易、券商或自动买卖能力。
- 开源仓库泄露绝对路径、持仓、token、Cookie 或 secret。

## P1 Current Milestone

### M1

- [x] 新增 V3 optional observation/product mapper，并以 legacy adapter 保持 `FundRecord` 和主 score/risk 不变。
- [x] 修复组合估值 missing 时的 `current_value=0` 和 `-100%`。
- [x] 建立产品 view model 和 diagnostics 分层。
- [x] 重组一级导航：市场、基金、自选、组合。
- [x] Research、Reports、System 降为二级。
- [x] 新增只读自选页。
- [x] 核心普通页面移除 raw provider/source code、schema、内部 warning code。
- [x] fixture 新闻默认不作为正式入口。
- [x] 完成 1440/768/375、a11y 基础检查和全量回归。
- [x] 行业日线使用 AKShare 精确同名 endpoint 回退；新增受控预热命令、cache 覆盖与用户层空态，真实 smoke 覆盖 `BK1042`、`BK1036`。
- [ ] 完成 PR、CI、clean `main` 验收和 `v3.0.0-alpha.1` 发布门禁。
- [x] 用 v2.6 fixture score/risk snapshot 与离线 daily/weekly 回归证明主模型、Research/Evidence 不变；live smoke 仍按对应数据 Milestone 单独执行。

### M2-M6

按 `docs/roadmap/v3-delivery-roadmap.md` 执行。当前 Milestone 未通过前不展开实现。

## P2 Later Polish

- 基金表格列设置持久化。
- 更丰富的图表 tooltip 和区间对比。
- 同类基金对比篮子。
- 自选分组和备注的 Web 编辑。
- 深色主题。
- 导出 CSV/PDF。
- 键盘快捷键。
- 指数和板块更多热力图。
- 当东方财富行业日线不可用且不存在 AKShare 同名板块时，补齐该板块的独立历史来源或正式标注不可用范围；不得用近似行业替代。
- 基金详情 SEO/分享链接（仅在未来公网方案明确后）。
- 本地通知。

## V3 之外

- 真实新闻/公告 provider 与内容许可。
- 多源自动核验。
- SaaS、多用户、账号和云同步。
- 移动端、小程序。
- 自动推荐。
- 自动交易和券商接入。
- 收益承诺或排名营销。
