# V2 Research Copilot 任务清单

## Batch 0：基线与规划

- [x] `T000` 发布 `v1.0.3` weekly scheduler 修复。
  映射：`AC-022`、`AC-024`
  验收：PR #22、CI、weekly `last exit code=0`、tag `v1.0.3`。
- [x] `T001` 冻结 V2 设计、架构、roadmap、spec 和执行契约。
  映射：全部 AC
  验收：文档一致性检查和规划 PR。

## Batch 1：M1 Research Data Access

- [x] `T101` 新增 ArtifactDescriptor 和 artifact registry。
  映射：`AC-001`、`AC-002`
  验收：白名单 artifact discovery 测试。
- [x] `T102` 新增 contract-aware loader 和安全降级。
  映射：`AC-003`
  验收：缺失/损坏/旧 schema/未知字段测试。
- [x] `T103` 新增 ResearchContext 和 topic query service。
  映射：`AC-004`
  验收：market/fund/portfolio/news/history/quality 单测。
- [x] `T104` 新增 `research-query` CLI 和 JSON 输出。
  映射：`AC-004`
  验收：CLI exit code、输出路径和不解析 Markdown 测试。
- [x] `T105` 新增 research-context contract、文档和 validator。
  映射：`AC-005`、`AC-021`
  验收：valid/invalid/old optional/unknown field contract 测试。
- [x] `T106` 完成 M1 回归、文档、PR、CI、运行验收和 `v1.1.0` tag。
  映射：`AC-022`、`AC-023`、`AC-025`

## Batch 2：M2 Evidence & Citation

- [x] `T201` 新增 EvidenceRef、ResearchFinding 和 EvidenceBundle。
  映射：`AC-006`、`AC-009`
- [x] `T202` 新增 JSON Pointer citation resolver。
  映射：`AC-006`
- [x] `T203` 新增 quality/conflict gate。
  映射：`AC-007`、`AC-008`
- [x] `T204` 新增 Evidence Graph 和 topic finding builders。
  映射：`AC-006`、`AC-007`、`AC-008`
- [x] `T205` 新增 `build-research-evidence` CLI、contract 和输出。
  映射：`AC-009`、`AC-021`
- [x] `T206` 完成 M2 回归、文档、PR、CI、运行验收和 `v1.2.0` tag。

## Batch 3：M3 Research Copilot Core

- [x] `T301` 新增 intent taxonomy 和交易/越界 intent guard。
  映射：`AC-010`、`AC-013`
- [x] `T302` 新增确定性 Research Planner。
  映射：`AC-010`、`AC-012`
- [x] `T303` 新增 ResearchAnswer 和模板化中文 renderer。
  映射：`AC-011`、`AC-012`
- [x] `T304` 新增 optional LLM renderer interface 和不可变事实校验。
  映射：`AC-014`
- [x] `T305` 新增 `research-ask` CLI、audit 和 contract。
  映射：`AC-010` 至 `AC-014`、`AC-021`
- [x] `T306` 完成六类问题 e2e、PR、CI、运行验收和 `v1.3.0` tag。

## Batch 4：M4 Read-only Skill / MCP

- [x] `T401` 核对官方 MCP SDK 并冻结 adapter contract。
  映射：`AC-015` 至 `AC-017`
- [x] `T402` 新增 optional MCP dependency 和只读 tools。
  映射：`AC-015`
- [x] `T403` 新增 path/write/trading/prompt-injection 防护。
  映射：`AC-016`
- [x] `T404` 新增脱敏 audit、错误分类和超时。
  映射：`AC-017`
- [x] `T405` 执行 skill governance review 并新增 Research Skill。
  映射：`AC-015` 至 `AC-017`
- [x] `T406` 完成 MCP permission、optional dependency、PR、CI、运行验收和 `v1.4.0` tag。

## Batch 5：M5 Copilot Console

- [x] `T501` 用 frontend design workflow 设计 Copilot 页面状态和导航。
  映射：`AC-018` 至 `AC-020`
- [x] `T502` 新增 question/answer/finding/citation/data-gap UI。
  映射：`AC-018`
- [x] `T503` 新增 review 和 audit UI。
  映射：`AC-018`
- [x] `T504` 保持全部 V1 页面和 service boundary。
  映射：`AC-019`
- [x] `T505` 完成空/错/加载/无 LLM、Playwright、截图和 a11y 验收。
  映射：`AC-020`
- [x] `T506` 完成 PR、CI、运行验收和 `v1.5.0` tag。

## Batch 6：M6 Release Hardening

- [x] `T601` 完成 V1/V2 contract 和旧 artifact 兼容矩阵。
  映射：`AC-021`、`AC-022`
- [x] `T602` 完成安全、隐私、prompt injection、路径隔离和只读审查。
  映射：`AC-013` 至 `AC-017`、`AC-025`
- [x] `T603` 完成性能预算和大 outputs 验证。
  映射：`AC-023`
- [x] `T604` 完成 fixture/live optional/daily/weekly/scheduler/Web/MCP e2e。
  映射：`AC-022` 至 `AC-024`
- [x] `T605` 更新 README、migration、ops、contracts、release report，发布 `v2.0.0-rc.1`。
  状态：PR #29、#30、#31 已完成，RC tag 绑定 `aaf526fa6d67b6933a67b908021df9419a83c786`。
- [x] `T606` 观察至少 3 个有效 daily run 并清零 P0/P1。
  映射：`AC-024`
- [x] `T607` fresh final verification、PR/CI/merge，发布 `v2.0.0`。
  状态：PR #33 合并为 `f419453ec3a21592ff4cad7c542a2846b290002e`，`v2.0.0` tag 与 post-release ops check 已完成。
  映射：全部 AC
