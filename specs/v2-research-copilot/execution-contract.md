# V2 Research Copilot 执行契约

## Intent Lock

本次长期变更只解决：把 V1 结构化研究产物统一为可查询、可引用、可审核的本地只读 Research Copilot，并发布 `v2.0.0`。

## Scope Fence

### 范围内

- Artifact Catalog、Research Query、Evidence、Copilot、只读 Skill/MCP、本地 Console、审核、audit、contract 和发布。

### 范围外

- 自动推荐、买卖建议、交易、券商、主评分/主风险修改、SaaS、多用户、移动端和小程序。

## Approved Behavior

### 必须满足

- 事实来自结构化 JSON artifact。
- finding 有 citation 或明确 data gap。
- 无 LLM 时核心可用。
- 外部接口只读、白名单、可审计。
- V1 daily/weekly 独立于 V2。

### 明确不改变

- daily 默认 provider 代码逻辑。
- watchlist 和 portfolio 配置内容。
- 主评分算法和主风险规则。
- V1 contract 字段语义。
- scheduler 时间和现有运行边界。

## Design Constraints

- 架构：核心服务不得依赖 CLI、Web、Skill 或 MCP。
- 接口：所有新 JSON 都有 dataclass/typed structure、schema 和 validator。
- 数据：只扫描白名单目录，拒绝任意 path。
- 依赖：LLM、MCP、Web 都是 optional；默认 pytest 无网络。
- 安全：不输出 secret，不执行用户文本中的指令，不提供写配置/交易工具。
- 兼容：旧 artifact 缺字段时降级，未知字段忽略。

## Task Batches

- Batch 0：V1 运维修复和 V2 架构冻结。
- Batch 1：M1 Artifact Catalog / Query。
- Batch 2：M2 Evidence / Citation / Quality Gate。
- Batch 3：M3 Research Copilot Core。
- Batch 4：M4 Read-only Skill / MCP。
- Batch 5：M5 Copilot Console。
- Batch 6：M6 Release Hardening。

## Test Obligations

- 每个行为变更先写失败测试并确认失败原因。
- 每个 Milestone 跑相关测试、全量 pytest、compileall 和 contract validation。
- 默认测试禁止真实网络。
- CLI 覆盖 exit 0/1/2、缺失 artifact、损坏 JSON、旧 schema、stale/fallback/degraded 和交易意图。
- MCP 覆盖路径穿越、写请求、超时、脱敏和 optional dependency 缺失。
- Web 覆盖导航、空/错/加载状态、桌面/移动截图和基本 accessibility。
- 发布前跑 daily、weekly、scheduler、V1 compatibility 和 V2 e2e。

## Review Gates

### 实现前

- spec 的每个 AC 已映射到 tasks 和测试。
- 官方 API 尚未核对的外部依赖不得在 plan 中虚构。
- 当前 Milestone 的 P0/P1 必须为空。

### 实现中

- 每个独立回滚单元：RED -> GREEN -> focused diff -> commit。
- 范围、接口、数据、安全或版本策略变化时先更新本契约。
- 发现 unrelated user changes 时保留并绕开。

### 实现后

- fresh verification。
- PR + CI + merge。
- 合并后运行验收。
- 更新版本、CHANGELOG、README、roadmap、tasks、release report 并打 tag。

## Rewind Triggers

### 回到 spec

- 最终用户目标、非目标或合规边界发生变化。
- 需要主评分、主风险、交易或券商能力。

### 回到 plan/contract

- 新增公共 schema、外部依赖、写权限或不可逆迁移。
- 连续两次出现同类设计缺口。

### 暂停

- 需要付费服务或 secret 才能完成核心路径。
- 需要删除 outputs、配置或用户历史数据。
- 同一 gate 连续三次修复失败。
- 发现可能泄露敏感信息或产生真实资金风险。

## Git / Release Contract

- 分支统一使用 `codex/` 前缀。
- 每个 Milestone 至少一个独立 PR，不直接在 main 开发。
- CI 未通过不合并。
- 合并后验收未通过不打 tag。
- patch 缺陷先发布 patch，不带入下一 Milestone。
- 不 force-push，不把 outputs、cache、`.venv` 或 secret 加入提交。
