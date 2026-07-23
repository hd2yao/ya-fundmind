# V2 Todo

## 规则

- `P0 blocking`：安全边界、数据破坏、主流程失败、contract 破坏、测试失败。立即停止当前 Milestone 并修复。
- `P1 current milestone`：当前 Milestone 的必做功能、CLI、contract、页面或验收缺失。不得跨 Milestone。
- `P2 later polish`：视觉、字段、筛选、性能和体验增强。不阻塞当前 gate。
- 新想法先判断是否服务 V2 最终目标；不服务则继续留在 ideas，不顺手扩范围。

## 当前状态

- 当前稳定版本：`v2.1.0` Local Product Web + Fund Explorer。
- 当前开发轨道：`v2.2 Fund Data Terminal`。
- 当前 Milestone：M1 单基金历史闭环已通过本地验收，下一步进入 M2 指数走势。
- 当前 P0：无。
- 当前 P1：指数日线、市场页指数图表及其缓存/API/真实 smoke。

## P0 Blocking

当前无已知 P0。

判定包括：

- daily/weekly 无法运行。
- pytest、compileall 或 contract validation 失败。
- V2 能修改 watchlist、portfolio、主评分、主风险、scheduler 或交易状态。
- 任意路径读取、敏感信息泄露或 prompt injection 能突破只读边界。
- V1 artifact 不兼容或被 V2 覆盖。

## P1 Current Milestone

`v2.2 M1` 已完成：

- 任意全市场搜索结果的历史净值按需获取。
- AKShare 历史净值规范化、坏行隔离和 SQLite 缓存。
- 新鲜缓存命中、live 获取、stale fallback 和无数据 503。
- `1m / 3m / 6m / 1y / all` 曲线和数据新鲜度摘要。
- 真实 `021511` smoke：6m 120 点，首次 live 后第二次缓存命中。
- 375/768/1440 页面、console error 和横向溢出检查。

`v2.2 M2` 必做：

- 建立独立市场时间序列模型，不复用 `fund_navs` 存储指数 OHLCV。
- 接入上证指数、沪深 300、创业板指日线。
- 提供固定 symbol allowlist 的指数历史 API。
- 市场页展示指数折线图、时间窗口、source/as_of/stale。
- 默认 pytest 不访问网络，真实 smoke 与 scheduler 隔离。

以下边界不是 P1：多源自动核验、Sites、公网部署、账号、云同步、推荐和自动交易。

## v2.0 Final 记录

以下 Final 门已完成：

- RC PR/CI/merge 和 `v2.0.0-rc.1` tag。
- 三个不同日期的真实 daily scheduler run provenance、AKShare live 和数据质量检查。
- `post_rc` 模式 `outputs/release/v2_release_readiness.json` 通过。

Final fresh verification、PR #33、Python 3.10/3.12 CI、merge commit、clean `main` smoke、`v2.0.0` tag 和 post-release ops check 均已完成。

## P2 Later Polish

- Artifact Catalog 增量扫描和文件监视。
- 更丰富的 evidence graph 可视化。
- 更多预设问题和 query filters。
- Copilot 回答导出 PDF。
- Console 主题和布局个性化。
- 更细的 audit 检索和 retention。
- 多语言 renderer。
- 更丰富的非交易型情景比较。
- Product Web 的高级图表、主题个性化、收藏编辑和跨设备访问。
- 在后续 Streamlit 升级前，把 `use_container_width` 调用迁移到 `width="stretch"/"content"`，消除 1.59 服务端弃用提示。

## 仍留在 Ideas 的事项

- 自动推荐。
- 自动交易和券商接入。
- SaaS、多用户、移动端、小程序。
- 投资博主人格化输出。

这些事项不进入 V2 Research Copilot 主线。
