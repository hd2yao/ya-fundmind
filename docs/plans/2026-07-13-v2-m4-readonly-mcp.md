# V2 M4 Read-only Skill / MCP Implementation Plan

## 目标

通过受控、可审计、optional 的只读 adapter，把 M1-M3 Research Query、Evidence 和 Copilot 暴露为 status、catalog、query、ask、evidence 五个 MCP tools，并交付仓库内 Research Skill，发布 `v1.4.0`。

## 官方 SDK 结论

核对日期：2026-07-13。

- MCP Python SDK `main` 当前是 v2 beta，官方明确提示 beta 仍可能破坏兼容，不应直接作为稳定生产依赖。[官方 Python SDK README](https://github.com/modelcontextprotocol/python-sdk)
- 官方 v1.x 分支是当前稳定维护线，并建议依赖添加 `<2` 上界；当前最新稳定发布为 `v1.28.1`。[官方 v1.x README](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x)
- 本项目使用 optional dependency `mcp>=1.28.1,<2`，默认安装、daily/weekly 和 CI 不安装 MCP。
- 使用 `mcp.server.fastmcp.FastMCP`；默认本地 transport 为 stdio，不启动公网 HTTP。[官方 server 文档](https://github.com/modelcontextprotocol/python-sdk/blob/v1.x/docs/server.md)
- tool 返回 typed `dict[str, Any]` structured output；预期错误转换为 `ToolError`。
- optional integration 使用官方 `create_connected_server_and_client_session` in-memory transport，不需要网络。[官方 testing 文档](https://github.com/modelcontextprotocol/python-sdk/blob/v1.x/docs/testing.md)

## Skill 治理结论

- Skill：`ya-fundmind-research`
- 结论：仓库内项目 Skill，手动调用；不安装到全局，不写入全局 `AGENTS.md`。
- 理由：只适用于 YA FundMind 的本地 artifact contract、CLI 和 MCP tools，不是跨项目入口型工作流。
- 路径：`skills/ya-fundmind-research/`。
- 需要：精简 `SKILL.md`、`agents/openai.yaml`、quick validation、真实只读调用验证。
- 不需要：全局安装、通用文件系统能力、独立 README、脚本复制或全局默认触发。

## Adapter Contract

### Tools

| Tool | 参数 | 服务边界 |
| --- | --- | --- |
| `status` | 无 | 只读 Artifact Catalog，返回可用主题和边界。 |
| `catalog` | `artifact_type?`、`limit?` | 只返回 registry 已发现 descriptor，不接收 path。 |
| `query` | `topic`、`code?` | 只调用 `ResearchQueryService`。 |
| `ask` | `question` | 只调用 `ResearchCopilot`，交易 intent 仍返回 refused。 |
| `evidence` | `topic`、`code?` | Query 后调用 `build_evidence_bundle`。 |

所有工具返回 `McpToolResult`：`schema_version`、`generated_at`、`generator`、`tool`、`status`、`data`、`warnings` 和 read-only metadata。

### 参数约束

- `topic` 只能是 market、fund、portfolio、news、history、quality。
- `code` 只允许 fund topic 且必须是 6 位数字。
- `question` 必须非空且最长 1000 字符。
- `artifact_type` 必须来自 registry；`limit` 为 1-200。
- tool 参数不允许 path、output_dir、config、command、URL 或写操作。

### 错误分类

- `invalid_argument`
- `unsupported_tool`
- `artifact_unavailable`
- `timeout`
- `audit_unavailable`
- `dependency_missing`
- `internal_error`

错误信息不包含 traceback、绝对路径、secret 或原始异常详情。

### Audit / Timeout

- 默认 timeout 10 秒，可由 server 启动参数调整，必须大于 0 且不超过 60 秒。
- gateway 使用 async timeout 包装只读 adapter；超时只终止本次响应，不修改任何状态。
- audit 默认写 `outputs/audit/mcp_calls.jsonl`。
- 记录 tool、时间、duration、status、error code、参数摘要和结果计数。
- question 只记录 SHA-256 和脱敏预览；token、password、API key、Bearer、Cookie 不落盘。

## 实现批次

### Task 1：Core Adapter

1. 先写 status/catalog/query/ask/evidence、参数白名单和只读边界失败测试。
2. 实现 `McpToolResult`、`McpAdapterError` 和 `ResearchMcpAdapter`。
3. 验证 blocked transaction、path/write/prompt-injection 请求不能越界。
4. Commit：`feat: add readonly research mcp adapter`。

### Task 2：Gateway / Audit / Timeout

1. 先写 timeout、错误分类、append-only audit 和 secret redaction 测试。
2. 实现 async `McpToolGateway` 和 MCP audit。
3. Commit：`feat: add mcp gateway audit and timeout`。

### Task 3：Optional FastMCP / CLI

1. 先写 dependency missing 和 server registration 测试。
2. 新增 optional dependency、`fund_agent/mcp_server.py` 和 `mcp-server` CLI。
3. 默认 pytest 不安装 MCP；optional 环境跑官方 in-memory session，确认只有五个工具。
4. Commit：`feat: add optional fastmcp server`。

### Task 4：Project Research Skill

1. 使用官方 skill initializer 创建 `skills/ya-fundmind-research`。
2. 写明只读调用顺序、证据检查、人工复核和禁止事项。
3. quick validation 和真实 M3/M4 调用验证。
4. Commit：`feat: add ya fundmind research skill`。

### Task 5：Release

1. 更新 MCP/Skill 文档、README、CHANGELOG、roadmap、tasks、backlog、version 和 release report。
2. 全量 pytest、compileall、demo/daily/contract/Web、M1-M4 e2e。
3. PR/CI/merge，main 验收后 tag `v1.4.0`。

## Gate

- `AC-015` 至 `AC-017` 满足。
- MCP/Skill 只调用公开 Catalog/Query/Copilot/Evidence 服务。
- 任意路径、写操作、配置修改、交易和券商请求不能成为工具能力。
- 所有调用可审计且不记录 secret。
- 无 MCP 依赖时 V1、M1-M3 CLI 和默认 CI 正常。
- optional MCP in-memory integration 真实通过。
- 不修改主评分、主风险、provider 默认、watchlist、portfolio 或 scheduler。
