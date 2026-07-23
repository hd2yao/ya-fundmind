# V2 Todo

## 规则

- `P0 blocking`：安全边界、数据破坏、主流程失败、contract 破坏、测试失败。立即停止当前 Milestone 并修复。
- `P1 current milestone`：当前 Milestone 的必做功能、CLI、contract、页面或验收缺失。不得跨 Milestone。
- `P2 later polish`：视觉、字段、筛选、性能和体验增强。不阻塞当前 gate。
- 新想法先判断是否服务 V2 最终目标；不服务则继续留在 ideas，不顺手扩范围。

## 当前状态

- 当前稳定版本：`v2.1.0` Local Product Web + Fund Explorer。
- 当前开发轨道：`v2.2 Fund Data Terminal`。
- 当前 Milestone：M3 行业板块走势已通过本地功能与三视口验收，下一步进入 M4 数据终端信息架构重组。
- 当前 P0：无。
- 当前 P1：M4 行情总览、基金终端、组合和研究证据四个工作区的信息架构与导航收敛。

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

`v2.2 M2` 已完成：

- SQLite `market_series` 独立保存指数 OHLCV、成交额、涨跌幅和新鲜度。
- AKShare 东方财富指数端点失败时可切换到同一 provider 的新浪端点，并保留完整 endpoint trace。
- `GET /api/market/indices/{symbol}/history` 支持固定 allowlist 和 `1m / 3m / 6m / 1y / all`。
- 市场页支持上证指数、沪深 300、创业板指切换、日线曲线和可折叠 OHLC 数据表。
- 真实 smoke、fresh cache 命中、375/768/1440 响应式和无 console error 验收通过。

`v2.2 M3` 必做：

- 建立行业板块标识与 AKShare 板块历史接口的稳定映射。
- 复用 `market_series` 保存板块日线，不混入基金净值或指数序列。
- 提供板块列表、板块历史和板块详情 API，保持固定参数边界。
- 把现有主题窗口统计与真实板块曲线建立可解释跳转，不输出板块推荐。
- 保持默认测试离线，并完成至少一个真实板块 smoke 和三视口验收。

`v2.2 M3` 已完成：

- SQLite `market_entities` 独立保存行业板块目录，`market_series` 以 `series_type=industry` 保存历史 OHLCV。
- AKShare 行业目录和历史字段完成标准化、坏行隔离、provider health、endpoint trace 与 cache 统计。
- `GET /api/market/sectors` 支持名称/`BK` 代码搜索及分页；`GET /api/market/sectors/{symbol}/history` 支持固定代码边界和五档交易日窗口。
- 市场页支持目录检索、板块选择、当前行情摘要、历史曲线和来源/新鲜度/质量状态。
- 主题窗口表可以发起同名行业板块搜索，但不将主题与板块强制等同。
- 375/768/1440 三视口交互验收、无页面横向溢出和无浏览器 console error。
- 真实 AKShare 行业 smoke 已执行但未成功：当前开发环境访问东方财富接口时发生代理连接中断；未伪造 live 成功，功能以离线测试、缓存降级和受控浏览器 fixture 验收通过。

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
- 行业板块目录增加翻页或“加载更多”，支持不修改关键词的失败重试。
- 补充行业板块请求竞态和移动端实际溢出的自动化回归测试。
- 在后续 Streamlit 升级前，把 `use_container_width` 调用迁移到 `width="stretch"/"content"`，消除 1.59 服务端弃用提示。

## 仍留在 Ideas 的事项

- 自动推荐。
- 自动交易和券商接入。
- SaaS、多用户、移动端、小程序。
- 投资博主人格化输出。

这些事项不进入 V2 Research Copilot 主线。
