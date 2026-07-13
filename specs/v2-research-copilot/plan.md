# V2 Research Copilot 实现方案

## 推荐方案

采用“V1 artifact -> Artifact Catalog -> Query Service -> Evidence -> Copilot -> Interfaces”的单向分层。核心功能使用标准库实现，Web、MCP 和 LLM 保持 optional dependency。

## 第一性原理评审

- 真实目标：减少用户在多份报告之间查找事实的成本，同时提升结论可追溯性。
- 最小可用结果：先提供统一结构化查询，而不是先做聊天 UI。
- 真实约束：本地、只读、兼容 V1、默认无网络、不能产生交易行为。
- 更简单路径：先用确定性 intent 和 renderer 覆盖高频问题；LLM 只作为后续可选渲染器。

## 架构和数据流

```text
V1 JSON artifact
-> ArtifactCatalog / ContractAwareLoader
-> ResearchQueryService / ResearchContext
-> EvidenceGraph / QualityGate
-> ResearchCopilot / ResearchAnswer
-> CLI / Skill / MCP / Console
-> Review / Audit
```

## 预计变更文件

### M1

- Create: `fund_agent/artifacts.py`
- Create: `fund_agent/research_query.py`
- Modify: `fund_agent/models.py`
- Modify: `fund_agent/cli.py`
- Modify: `fund_agent/contract.py`
- Create: `docs/contracts/research-context-v1.md`
- Create: `tests/test_artifact_catalog.py`
- Create: `tests/test_research_query.py`
- Create: `tests/test_research_query_cli.py`

### M2

- Create: `fund_agent/research_evidence.py`
- Modify: `fund_agent/models.py`
- Modify: `fund_agent/cli.py`
- Modify: `fund_agent/contract.py`
- Create: `docs/contracts/evidence-bundle-v1.md`
- Create: `tests/test_research_evidence.py`
- Create: `tests/test_quality_gate.py`

### M3

- Create: `fund_agent/research_copilot.py`
- Create: `fund_agent/copilot_renderer.py`
- Create: `fund_agent/audit.py`
- Modify: `fund_agent/models.py`
- Modify: `fund_agent/cli.py`
- Modify: `fund_agent/contract.py`
- Create: `docs/contracts/research-answer-v1.md`
- Create: `tests/test_research_copilot.py`
- Create: `tests/test_research_guardrails.py`
- Create: `tests/test_research_ask_cli.py`

### M4

- Create: MCP adapter file after official SDK review; expected module boundary `fund_agent/mcp_server.py`.
- Modify: `pyproject.toml` optional dependencies only.
- Create: MCP permission and optional dependency tests.
- Create/update Research Skill source after `skill-governance-review`.

### M5

- Modify: `fund_agent/web_console.py`
- Modify: `fund_agent/cli.py` only if startup options are required.
- Create/update Web state, navigation, screenshot and accessibility tests.

### M6

- Modify: README, CHANGELOG, project structure, architecture, roadmap, ops and contracts.
- Create: migration guide and `docs/releases/v2.0.0-release-report.md`.
- Update: end-to-end, compatibility, performance and security tests.

## 测试和验证

- 单元：catalog、loader、query、evidence、quality、intent、guardrail、renderer、audit。
- contract：valid、missing required、old optional、unknown field、schema mismatch。
- CLI：成功、partial、unsupported、invalid args、missing output、exit policy。
- 安全：path traversal、write request、trading request、prompt injection、secret redaction。
- UI：导航、空/错/加载状态、桌面/移动截图、基本 accessibility。
- 回归：V1 daily/weekly、fixture、report、snapshot、trace、dashboard、Web Console。

## 风险和回滚

- schema 扩散：每个新输出独立 contract，V1 schema 不改语义。
- CLI 膨胀：业务逻辑放 service module，CLI 只做参数和 I/O。
- LLM 幻觉：LLM 不进入事实选择和质量门；输出后校验不可变字段。
- MCP 权限：白名单 tools 和 path；核心服务不接受任意 path。
- Web 重复逻辑：Console 只调用公共 service。
- 回滚：每个 Milestone 有独立 tag；失败可回退到前一 tag，outputs 只新增目录。

## 执行契约

详细约束见 `specs/v2-research-copilot/execution-contract.md`。每个 Milestone 开始前生成细化 TDD plan，结束后做 AC 收敛检查。
