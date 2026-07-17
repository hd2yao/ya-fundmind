# V2 Delivery Roadmap

## 交付目标

在不破坏 V1 daily/weekly 和研究边界的前提下，把 YA FundMind OS 从“自动生成多份研究材料”升级为“能够基于本地证据回答研究问题的只读 Research Copilot”，最终发布 `v2.0.0`。

## 版本和发布规则

| 阶段 | 版本 | 发布含义 |
| --- | --- | --- |
| V1 修复 | `v1.0.3` | weekly scheduler 恢复，已完成 |
| M1 | `v1.1.0` | 统一数据访问可用 |
| M2 | `v1.2.0` | 证据引用和质量门可用 |
| M3 | `v1.3.0` | Research Copilot CLI 可用 |
| M4 | `v1.4.0` | 只读 Skill/MCP 可用 |
| M5 | `v1.5.0` | 本地 Copilot Console 可用 |
| M6 RC | `v2.0.0-rc.1` | V2 候选发布，技术门完成 |
| V2 Final | `v2.0.0` | 全部验收通过，发布执行中 |

每个 Milestone 必须：

1. 从最新 `main` 创建 `codex/` 分支和独立 worktree。
2. 先写失败测试，再实现最小行为。
3. 完成 focused diff review、全量 pytest、compileall 和相关 contract/CLI 验证。
4. 更新 README、CHANGELOG、roadmap、tasks 和 release report。
5. 推送分支并创建 PR；CI 通过后合并。
6. 在合并后的 `main` 上做运行验收，再创建并推送 tag。
7. P0/P1 未清零不得进入下一 Milestone；P2 写入 `docs/backlog/v2-todo.md`。

## M0：V1 Ops 修复（`v1.0.3`，已完成）

### 目标

修复 weekly launchd 在精简 PATH 下找不到 `python` 的问题。

### 验收证据

- PR #22 已合并。
- weekly plist 使用项目 `.venv/bin/python` 绝对路径。
- 真实 `launchctl` 触发：`runs=1`、`last exit code=0`。
- `217 passed`、compileall、contract、Web Console dry-run 通过。

## M1：Research Data Access（`v1.1.0`）

状态：完成。

### 目标

建立 V1 artifact 的统一目录和只读查询入口，让后续模块不再各自拼路径、猜字段或解析 Markdown。

### 必做任务

- 新增 `ArtifactDescriptor`、`ArtifactCatalog` 和白名单 artifact registry。
- 支持 report、snapshot、trace、market、fund detail、portfolio、news、ops、daily/weekly artifact。
- 新增 contract-aware JSON loader、缺失/损坏/旧 schema 安全降级。
- 新增 `ResearchContext` 和 market/fund/portfolio/news/history/quality 查询。
- 新增 CLI：`research-query`。
- 新增 JSON contract：`research-context-v1`。
- 输出 `outputs/research_queries/research_context.json`。

### 用户可见效果

用户和后续模块通过一个 CLI 和一个 JSON contract 获取研究上下文，不再手工打开多份文件。

### CLI

```bash
python -m fund_agent.cli research-query --output-dir outputs --topic market
python -m fund_agent.cli research-query --output-dir outputs --topic fund --code 021511
python -m fund_agent.cli research-query --output-dir outputs --topic portfolio
python -m fund_agent.cli research-query --output-dir outputs --topic news
python -m fund_agent.cli research-query --output-dir outputs --topic quality
```

### Gate

- 所有支持的 artifact 能被 catalog 发现并带 schema/as_of/quality metadata。
- 缺失、损坏和旧 artifact 不崩溃且有 warning。
- 查询结果不解析 Markdown。
- 当前 V1 contract validation、daily、weekly 和 Web Console 不回归。
- 新 contract validation 通过。

### 不做

- 不生成自然语言 Copilot 回答。
- 不引入 LLM、MCP 或新 Web UI。
- 不修改主评分和主风险。

## M2：Evidence & Citation（`v1.2.0`）

状态：完成。

### 目标

让每个研究 finding 都能定位到原始 JSON artifact 和字段，并统一处理数据质量、冲突和缺口。

### 必做任务

- 新增 `EvidenceRef`、`ResearchFinding` 和 `EvidenceGraph`。
- 生成 artifact id、JSON Pointer、as_of、source、quality、stale 引用。
- 新增 quality gate：normal/warning/degraded/blocked。
- 处理 stale、fallback、critical warning、样本不足和跨来源冲突。
- 新增 `evidence-bundle-v1` contract 和验证。
- 新增 CLI：`build-research-evidence`。
- 输出 `outputs/evidence/research_evidence.json`。

### 用户可见效果

每个关键结论都能展开查看“依据哪份数据、哪个字段、什么时间、质量如何”。证据不足时系统明确说不知道。

### Gate

- finding 有证据时至少包含一个有效 EvidenceRef。
- 没有证据时不能生成肯定结论。
- stale/fallback/degraded 正确降级。
- 冲突来源并列展示并设置 `review_required=true`。
- JSON Pointer 能定位到原字段。
- V1 输出不变。

### 不做

- 不做自然语言自由问答。
- 不修改评分、风险或交易边界。

## M3：Research Copilot Core（`v1.3.0`）

状态：完成。

### 目标

提供受约束的自然语言研究入口，把问题转换为确定性查询计划和结构化 ResearchAnswer。

### 必做任务

- 新增 intent taxonomy 和只读 planner。
- 支持 market、theme、fund、portfolio、news、history、quality、unsupported intents。
- 新增 `ResearchAnswer`、guardrails 和 disclaimer。
- 阻止买卖、仓位、收益承诺和交易请求。
- 新增确定性中文 renderer。
- 新增可选 LLM renderer interface，默认关闭；核心测试不依赖网络。
- 新增 CLI：`research-ask`。
- 新增 `research-answer-v1` contract。
- 写入 `outputs/copilot/research_answer.json/md` 和 audit event。

### 用户可见效果

用户可以直接问“今天市场有什么变化”“这只基金缺什么数据”“组合暴露在哪里”，系统给出有证据、可审核的回答。

### Gate

- 六类核心问题有端到端测试。
- 无 LLM 时完整可用。
- 每个关键 finding 有 citation 或明确 data gap。
- 交易型问题被安全拒绝。
- LLM 输出不能改变数值、证据和质量等级。
- 不覆盖主报告结论。

### 不做

- 不自动推荐、不修改主评分/风险、不做交易。

## M4：Read-only Skill / MCP（`v1.4.0`）

状态：完成。

### 目标

让外部 Agent/工具通过受控只读接口使用 V2 Research Copilot，而不是直接访问任意本地文件。

### 必做任务

- 先核对官方 MCP SDK/API，冻结本项目 adapter contract。
- 新增只读 MCP tools：status、catalog、query、ask、evidence。
- 工具参数使用白名单和路径隔离，不支持任意 path。
- 新增超时、错误分类、审计和敏感信息过滤。
- 新增 Research Skill，创建前执行 skill governance review。
- 默认安装和 CI 不要求 MCP/LLM 依赖；使用 optional dependency。
- 增加权限、prompt injection、路径穿越和只读测试。

### 用户可见效果

Codex 或其他兼容工具可以读取本地研究结果并获得证据引用，但不能修改配置或执行交易。

### Gate

- MCP/Skill 只调用公开 Query/Copilot service。
- 任意路径、写操作、配置修改请求被拒绝。
- 无 MCP 依赖时 V1/V2 CLI 正常。
- 所有调用可审计且不记录 secret。
- 默认 CI 无真实网络。

### 不做

- 不提供写工具、不接券商、不做通用文件系统 MCP。

## M5：Copilot Console（`v1.5.0`）

状态：完成。

### 目标

把 Research Copilot、证据、质量和人工审核整合进本地 Web Console。

### 必做任务

- 在现有 Streamlit console 增加 Copilot 页面和导航。
- 支持提问、示例问题、回答摘要、finding、citation 展开和 data gaps。
- 支持审核状态、审核备注和 audit 查看。
- 保留 Market/Funds/Portfolio/News/Review/Reports 页面。
- 增加空状态、加载状态、错误状态和无 LLM 降级状态。
- 做桌面/移动 viewport 截图和基础 accessibility 验证。
- Web 只调用 Copilot service，不重复业务逻辑。

### 用户可见效果

用户无需命令行即可完成问题提交、证据核对、质量检查和人工审核。

### Gate

- 首页和全部 V1/V2 导航可访问。
- 页面无重叠、裁切和空白状态缺失。
- 证据可展开并定位来源。
- UI 不包含买卖建议或交易入口。
- Playwright/截图和 Web 测试通过。

### 不做

- 不公网部署、不登录、不多用户、不做复杂 SaaS。

## M6：V2 Release Hardening（`v2.0.0-rc.1` -> `v2.0.0`）

状态：Final gate 通过，发布执行中。RC 技术实现、兼容、安全、性能、端到端和文档门已完成；2026-07-15、2026-07-16、2026-07-17 三个 post-RC scheduler run 通过 provenance、AKShare live、数据质量和 strict contract 门。

### 目标

完成兼容、安全、性能、文档、迁移和真实本地运行验收，发布 V2。

### 必做任务

- 完成 contract、CLI、MCP、Web、audit 和无 LLM 端到端矩阵。
- 运行 fixture、AKShare 可选 smoke、daily、weekly 和 scheduler 验收。
- 验证旧 V1 outputs、旧 schema 和缺失字段兼容。
- 增加性能预算：catalog/query/answer 在本地典型 outputs 下可交互使用。
- 完成敏感信息、路径隔离、prompt injection 和只读边界审查。
- 编写 V1 -> V2 迁移说明、用户手册、故障排查和 release report。
- RC 合并后观察至少 3 个不同日期的有效 daily scheduler run；发现 P0/P1 只发 patch RC。

### 用户可见效果

V2 可以稳定作为日常本地研究入口，同时 V1 自动任务和所有原页面继续可用。

### Final Gate

- P0/P1 为 0。
- 全量 pytest、compileall、contract validation、CLI e2e、Web screenshot、MCP permission tests 全部通过。
- daily 和 weekly launchd 最近退出码为 0。
- V1 核心 artifact 可继续读取。
- 六类核心问题完成验收。
- `main_score_changed=false`、`main_risk_changed=false`。
- 没有交易、券商、买卖建议或收益承诺。
- README、CHANGELOG、architecture、roadmap、contracts、ops 和 release report 完整。
- 三个 run 的 `app_version=2.0.0rc1`、`git_commit=<RC main merge commit>`、`git_dirty=false`、`trigger=daily_ops/launchd/scheduler`。
- 三个 run 均为 AKShare live rows > 0，且无 fallback、critical warning 或 degraded quality。

### Release Readiness

RC 前兼容检查使用：

```bash
python -m fund_agent.cli release-readiness \
  --output-dir outputs \
  --release-target v2.0.0-rc.1 \
  --observation-mode historical_compat
```

Final 只能使用：

```bash
python -m fund_agent.cli release-readiness \
  --output-dir outputs \
  --release-target v2.0.0 \
  --observation-mode post_rc \
  --required-app-version 2.0.0rc1 \
  --required-git-commit "$(git rev-list -n 1 v2.0.0-rc.1)"
```

`historical_compat` 通过不等于 Final 通过，也不允许修改历史 run metadata 补门。

### Final 验收证据

- `post_rc status=pass`，有效 run 为 3/3，日期为 2026-07-15、2026-07-16、2026-07-17。
- 三个 run 均为 `app_version=2.0.0rc1`、精确 commit `aaf526fa6d67b6933a67b908021df9419a83c786`、`git_dirty=false`、`trigger=daily_ops`。
- AKShare live rows 分别为 19,987、21,546、21,536；无 fallback、critical warning 或 degraded quality。
- report、snapshot、trace strict contracts 与发布机性能预算通过。
- 产品化 React/FastAPI Web Console 保持独立 Draft PR，不进入本 Final 版本。

## 自主推进规则

用户已授权通过 gate 后自动进入下一 Milestone，不需要逐步确认。

只有以下情况暂停：

- 需要付费服务或用户 secret 才能完成核心功能。
- 需要改变主评分、主风险、交易边界或 V1 contract 语义。
- 存在数据删除、不可逆迁移或真实资金风险。
- 同一 gate 连续三次修复失败，需要重审架构。
