# V2 Todo

## 规则

- `P0 blocking`：安全边界、数据破坏、主流程失败、contract 破坏、测试失败。立即停止当前 Milestone 并修复。
- `P1 current milestone`：当前 Milestone 的必做功能、CLI、contract、页面或验收缺失。不得跨 Milestone。
- `P2 later polish`：视觉、字段、筛选、性能和体验增强。不阻塞当前 gate。
- 新想法先判断是否服务 V2 最终目标；不服务则继续留在 ideas，不顺手扩范围。

## 当前状态

- 当前版本：`v2.0.0` 已发布；`v2.1.0rc1` Product Web 正在独立验收。
- 当前 Milestone：Local Product Web + Fund Explorer。
- 当前 P0：无。
- 当前 P1：完成真实全市场数据、三视口和本地 launchd 验收，通过 PR/CI 后发布 RC。

## P0 Blocking

当前无已知 P0。

判定包括：

- daily/weekly 无法运行。
- pytest、compileall 或 contract validation 失败。
- V2 能修改 watchlist、portfolio、主评分、主风险、scheduler 或交易状态。
- 任意路径读取、敏感信息泄露或 prompt injection 能突破只读边界。
- V1 artifact 不兼容或被 V2 覆盖。

## P1 Current Milestone

`v2.1.0rc1` 待完成：

- 用最新真实 `market_intelligence_report.json` 验证 21,000+ 条服务端索引。
- 运行全量 pytest、compileall、strict contracts 和前端 typecheck/test/build。
- 完成 375/768/1440 页面截图、console error 和横向溢出检查。
- 安装独立 Web launchd 并验证 health、首页和重启。
- Draft PR #32 完成对抗式评审、CI、合并和 RC tag。

以下边界不是 P1：Sites、公网部署、账号、云同步和自动交易。

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
