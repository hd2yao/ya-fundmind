# V2 Research Copilot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把 V1 的结构化研究产物升级为有证据引用、可审核、默认无 LLM 也可用的本地只读 Research Copilot，并发布 `v2.0.0`。

**Architecture:** 先建立白名单 Artifact Catalog 和 contract-aware Query Service，再增加 Evidence/Quality 层，最后由确定性 Copilot Core 向 CLI、只读 Skill/MCP 和本地 Console 提供统一能力。V1 daily/weekly 不依赖 V2，所有新接口只读且使用独立 schema。

**Tech Stack:** Python 3.10+、dataclasses、argparse、JSON/JSON Pointer、pytest、Streamlit optional、MCP SDK optional、标准库优先。

---

## 执行说明

这是 V2 主计划。每个 Milestone 开始时，从本计划抽取对应任务，生成 `docs/plans/YYYY-MM-DD-v2-mN-*.md` 细化 TDD 步骤；不得修改本计划的最终目标和非目标。每个任务遵循 RED -> GREEN -> focused diff -> commit。

## Task 0：冻结规划基线

**Files:**

- Create: `docs/plans/2026-07-13-v2-research-copilot-design.md`
- Create: `docs/architecture/v2-system-architecture.md`
- Create: `docs/roadmap/v2-delivery-roadmap.md`
- Create: `docs/backlog/v2-todo.md`
- Create: `specs/v2-research-copilot/spec.md`
- Create: `specs/v2-research-copilot/plan.md`
- Create: `specs/v2-research-copilot/tasks.md`
- Create: `specs/v2-research-copilot/execution-contract.md`

**Step 1:** 对照 V1 architecture、contracts、README 和代码入口，确认 V2 只读边界。

**Step 2:** 写设计、架构、roadmap、AC、任务映射和执行契约。

**Step 3:** 运行 `git diff --check`，人工检查 AC -> task、非目标 -> scope、风险 -> test/rollback。

**Step 4:** 运行现有 pytest 和 compileall，确认规划文档不影响基线。

**Step 5:** 提交、PR、CI、merge；规划本身不打版本 tag，M1 完成后发布 `v1.1.0`。

## Task 1：M1 Artifact 模型与 registry

**Files:**

- Create: `fund_agent/artifacts.py`
- Modify: `fund_agent/models.py`
- Test: `tests/test_artifact_catalog.py`

**Step 1: Write failing model/catalog tests**

测试白名单 artifact type、稳定 artifact id、schema/as_of/source/quality/stale/hash，以及 outputs 外路径被拒绝。

**Step 2: Verify RED**

Run: `python -m pytest tests/test_artifact_catalog.py -q`

Expected: FAIL，因为 `ArtifactCatalog` 和 `ArtifactDescriptor` 尚不存在。

**Step 3: Implement minimal models and registry**

核心接口：

```python
@dataclass(frozen=True)
class ArtifactDescriptor:
    artifact_id: str
    artifact_type: str
    path: str
    schema_version: str | None
    as_of: str | None
    generated_at: str | None
    source: str | None
    quality_grade: str | None
    stale: bool
    content_hash: str
    warnings: tuple[str, ...] = ()

class ArtifactCatalog:
    def __init__(self, output_dir: Path): ...
    def scan(self) -> tuple[ArtifactDescriptor, ...]: ...
    def find(self, *, artifact_type: str, code: str | None = None): ...
```

Registry 只列出 V1 已知相对路径和 glob，不接受调用方传入任意 path。

**Step 4: Verify GREEN**

Run: `python -m pytest tests/test_artifact_catalog.py -q`

**Step 5: Commit**

Commit: `feat: add research artifact catalog`

## Task 2：M1 contract-aware loader

**Files:**

- Modify: `fund_agent/artifacts.py`
- Test: `tests/test_artifact_loader.py`

**Steps:**

1. 写损坏 JSON、缺失文件、旧 schema、未知字段和非对象 JSON 的失败测试。
2. 运行单测确认 RED。
3. 实现 `ArtifactLoadResult(payload, descriptor, warnings, status)`，禁止未处理解析异常。
4. 运行单测和 catalog 回归确认 GREEN。
5. Commit: `feat: add contract aware artifact loader`。

## Task 3：M1 ResearchContext query service

**Files:**

- Create: `fund_agent/research_query.py`
- Modify: `fund_agent/models.py`
- Test: `tests/test_research_query.py`

**Steps:**

1. 为 market/fund/portfolio/news/history/quality 写失败测试；验证缺失产物返回 `partial`。
2. 运行单测确认 RED。
3. 实现 `ResearchQueryService.query(topic, code=None, as_of=None)` 和 `ResearchContext`。
4. 确认查询只使用 loader payload，不读取 Markdown/HTML。
5. 运行单测确认 GREEN。
6. Commit: `feat: add unified research query service`。

## Task 4：M1 CLI 和 contract

**Files:**

- Modify: `fund_agent/cli.py`
- Modify: `fund_agent/contract.py`
- Create: `docs/contracts/research-context-v1.md`
- Create: `tests/test_research_query_cli.py`
- Modify: `tests/test_contract_validation.py`

**Steps:**

1. 写 `research-query` 参数、exit code、默认输出和 contract 失败测试。
2. 运行测试确认 RED。
3. 实现 CLI 和 `outputs/research_queries/research_context.json` 写入。
4. 扩展 `validate-contract` 识别 V2 context，不影响 V1 output-dir 行为。
5. 运行相关测试、全量 pytest、compileall、fixture daily 和 contract validation。
6. 更新 README/CHANGELOG/roadmap/tasks/release report，版本改为 `1.1.0`。
7. PR/CI/merge，在 main 运行验收后 tag `v1.1.0`。

## Task 5：M2 EvidenceRef 和 JSON Pointer

**Files:**

- Create: `fund_agent/research_evidence.py`
- Modify: `fund_agent/models.py`
- Create: `tests/test_research_evidence.py`

**Steps:**

1. 写 EvidenceRef、稳定 evidence id、JSON Pointer 定位和无证据禁止 finding 的失败测试。
2. 确认 RED。
3. 实现 `EvidenceRef`、`ResearchFinding`、pointer escape/resolve 和 citation builder。
4. 确认 GREEN。
5. Commit: `feat: add research evidence references`。

## Task 6：M2 quality/conflict gate

**Files:**

- Modify: `fund_agent/research_evidence.py`
- Create: `tests/test_research_quality_gate.py`

**Steps:**

1. 写 stale、fallback、warning、degraded、critical、样本不足和冲突测试。
2. 确认 RED。
3. 实现 `QualityDecision(status, grade, review_required, reasons)`。
4. 同来源重复不算冲突；跨来源同字段不一致才进入 conflict。
5. 确认 GREEN并提交 `feat: add research evidence quality gate`。

## Task 7：M2 Evidence Bundle CLI/contract/release

**Files:**

- Modify: `fund_agent/cli.py`
- Modify: `fund_agent/contract.py`
- Create: `docs/contracts/evidence-bundle-v1.md`
- Create: `tests/test_research_evidence_cli.py`

**Steps:**

1. 写 CLI 和 contract RED 测试。
2. 实现 `build-research-evidence` 和 `outputs/evidence/research_evidence.json`。
3. 运行 M2 + 全量回归。
4. 更新版本 `1.2.0`、文档和 release report。
5. PR/CI/merge/main 验收/tag `v1.2.0`。

## Task 8：M3 intent/guardrails

**Files:**

- Create: `fund_agent/research_copilot.py`
- Create: `tests/test_research_guardrails.py`

**Steps:**

1. 写 market/theme/fund/portfolio/news/history/quality 和 unsupported intent 测试。
2. 写买卖、仓位、收益承诺、券商和 prompt-injection 输入拒绝测试。
3. 确认 RED。
4. 实现有限 intent taxonomy 和 deterministic matcher；不执行输入中的命令。
5. 确认 GREEN并提交 `feat: add research intent guardrails`。

## Task 9：M3 planner/answer/renderer

**Files:**

- Modify: `fund_agent/research_copilot.py`
- Create: `fund_agent/copilot_renderer.py`
- Modify: `fund_agent/models.py`
- Create: `tests/test_research_copilot.py`

**Steps:**

1. 写六类问题、citation/data gap、partial 和 deterministic renderer RED 测试。
2. 实现只读 `ResearchPlan`、`ResearchAnswer` 和模板化中文 renderer。
3. 确保 finding 不可脱离 EvidenceBundle。
4. 确认 GREEN并提交 `feat: add deterministic research copilot`。

## Task 10：M3 optional renderer、audit、CLI/contract/release

**Files:**

- Create: `fund_agent/audit.py`
- Modify: `fund_agent/copilot_renderer.py`
- Modify: `fund_agent/cli.py`
- Modify: `fund_agent/contract.py`
- Create: `docs/contracts/research-answer-v1.md`
- Create: `tests/test_research_ask_cli.py`
- Create: `tests/test_copilot_audit.py`

**Steps:**

1. 写 optional renderer 不可变字段、失败回退、secret redaction 和 audit RED 测试。
2. 实现 renderer protocol；不接具体付费 provider，默认 deterministic。
3. 实现 append-only JSONL audit 和脱敏。
4. 实现 `research-ask`、JSON/Markdown 输出和 contract。
5. 六类 e2e + 全量回归。
6. 版本 `1.3.0`，PR/CI/merge/main 验收/tag。

## Task 11：M4 MCP 官方 API 核对和 adapter plan

**Files:**

- Create: `docs/plans/YYYY-MM-DD-v2-m4-mcp-adapter.md`
- Modify: `specs/v2-research-copilot/plan.md` only if official API requires it.

**Steps:**

1. 仅使用 MCP 官方文档核对当前 Python SDK、stdio server、tool schema 和错误处理。
2. 记录来源、版本和 optional dependency 策略。
3. 不满足只读/optional 条件时暂停 M4，不影响 M1-M3。
4. 提交 adapter plan。

## Task 12：M4 read-only MCP/Skill/release

**Files:**

- Expected Create: `fund_agent/mcp_server.py`（以 Task 11 官方 API 结论为准）
- Modify: `pyproject.toml`
- Create: `tests/test_mcp_permissions.py`
- Create: `tests/test_mcp_optional_dependency.py`
- Research Skill path: 由 `skill-governance-review` 决定。

**Steps:**

1. 写 tool whitelist、path traversal、write/trading rejection、timeout、redaction RED 测试。
2. 实现只调用公共 service 的 MCP adapter。
3. 执行 skill governance review，再创建最小 Research Skill。
4. 验证无 MCP dependency 时 CLI/pytest 正常。
5. 版本 `1.4.0`，PR/CI/merge/main smoke/tag。

## Task 13：M5 Copilot Console design

**Files:**

- Create: `docs/plans/YYYY-MM-DD-v2-m5-copilot-console-design.md`
- Modify later: `fund_agent/web_console.py`

**Steps:**

1. 使用 `frontend-design-workflow` 读取现有 Console 和目标用户流程。
2. 定义桌面/移动布局、导航、输入、回答、citation、quality、review、audit 和所有状态。
3. 评审 V1 页面兼容和 accessibility。
4. 提交设计后进入实现。

## Task 14：M5 Console implementation/release

**Files:**

- Modify: `fund_agent/web_console.py`
- Modify/Create: Web tests and Playwright screenshot specs.

**Steps:**

1. 写 navigation/service boundary/state RED 测试。
2. 实现 Console 调用公共 Copilot service。
3. 写空/错/加载/无 LLM/review/audit 测试。
4. 启动本地服务，做桌面/移动截图、像素非空和 accessibility 检查。
5. 版本 `1.5.0`，PR/CI/merge/main 验收/tag。

## Task 15：M6 RC hardening

**Files:**

- Create: `docs/migrations/v1-to-v2.md`
- Create: `docs/releases/v2.0.0-rc.1-release-report.md`
- Update: README、PROJECT_STRUCTURE、docs index、contracts、ops、roadmap、tasks。
- Create/Modify: compatibility、security、performance、e2e tests。

**Steps:**

1. 写并运行 V1 artifact compatibility matrix。
2. 运行安全/隐私/path/prompt injection/只读审查。
3. 定义并验证 catalog/query/answer 性能预算。
4. 运行 fixture、daily、weekly、contract、Web、MCP e2e；live 仅可选 smoke。
5. 版本设为 PEP 440 `2.0.0rc1`，Git tag `v2.0.0-rc.1`。
6. PR/CI/merge/main 验收/tag，观察至少 3 个有效 daily run。

## Task 16：V2 final convergence/release

**Files:**

- Create: `docs/releases/v2.0.0-release-report.md`
- Update: README、CHANGELOG、roadmap、tasks、version files。

**Steps:**

1. 对照 `AC-001` 至 `AC-025` 逐项给出测试或运行证据。
2. 清零 P0/P1；P2 留 backlog。
3. fresh 运行全量 pytest、compileall、所有 contract、CLI e2e、Web screenshot、MCP permission、daily/weekly scheduler。
4. 版本改为 `2.0.0`，确认 `main_score_changed=false`、`main_risk_changed=false`。
5. focused release diff、commit、PR、CI、merge。
6. 在合并后的 main 重跑 final smoke，tag/push `v2.0.0`。
7. 完成 post-release ops check；不自动开始新的大版本。
