# V2 Todo

## 规则

- `P0 blocking`：安全边界、数据破坏、主流程失败、contract 破坏、测试失败。立即停止当前 Milestone 并修复。
- `P1 current milestone`：当前 Milestone 的必做功能、CLI、contract、页面或验收缺失。不得跨 Milestone。
- `P2 later polish`：视觉、字段、筛选、性能和体验增强。不阻塞当前 gate。
- 新想法先判断是否服务 V2 最终目标；不服务则继续留在 ideas，不顺手扩范围。

## 当前状态

- 当前版本：`v2.0.0-rc.1`。
- 当前 Milestone：M6 RC 技术门已完成，正在完成 RC 发布和 Final post-RC 观察。
- 当前 P0：无。
- 当前 P1：发布 `v2.0.0-rc.1`；随后收集 3 个不同日期、满足 provenance 和数据质量门的 scheduler run，再发布 `v2.0.0`。

## P0 Blocking

当前无已知 P0。

判定包括：

- daily/weekly 无法运行。
- pytest、compileall 或 contract validation 失败。
- V2 能修改 watchlist、portfolio、主评分、主风险、scheduler 或交易状态。
- 任意路径读取、敏感信息泄露或 prompt injection 能突破只读边界。
- V1 artifact 不兼容或被 V2 覆盖。

## P1 Current Milestone

- 完成 RC PR/CI/merge 和 `v2.0.0-rc.1` tag。
- RC 合并后收集 3 个不同日期的真实 daily scheduler run；要求版本、commit、clean tree、trigger、AKShare live 和数据质量全部合格。
- 以 `post_rc` 模式生成通过的 `outputs/release/v2_release_readiness.json`。
- P0/P1 清零后完成 Final PR/CI/merge、fresh verification 和 `v2.0.0` tag。

## P2 Later Polish

- Artifact Catalog 增量扫描和文件监视。
- 更丰富的 evidence graph 可视化。
- 更多预设问题和 query filters。
- Copilot 回答导出 PDF。
- Console 主题和布局个性化。
- 更细的 audit 检索和 retention。
- 多语言 renderer。
- 更丰富的非交易型情景比较。

## 仍留在 Ideas 的事项

- 自动推荐。
- 自动交易和券商接入。
- SaaS、多用户、移动端、小程序。
- 投资博主人格化输出。

这些事项不进入 V2 Research Copilot 主线。
