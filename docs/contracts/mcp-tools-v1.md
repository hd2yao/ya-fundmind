# Read-only Research MCP Tools Contract v1

## Schema Version

- Tool result `schema_version`: `"1.0"`
- `generator`: `"fund_agent"`
- Server name：`YA FundMind Research`
- 默认 transport：`stdio`
- 默认 audit：`outputs/audit/mcp_calls.jsonl`

## 用途

本 contract 让 MCP host 通过五个受控工具读取 YA FundMind 的本地结构化研究结果。工具只调用 Artifact Catalog、Research Query、Evidence Bundle 和 Research Copilot，不接受任意文件路径，不解析 Markdown，不修改配置或业务状态。

MCP 是 optional adapter。没有 MCP 依赖时，daily、weekly、CLI、Web Console 和 M1-M3 输出继续可用。

## Optional Dependency

```bash
pip install -e ".[mcp]"
python -m fund_agent.cli mcp-server --output-dir outputs --dry-run
python -m fund_agent.cli mcp-server --output-dir outputs
```

依赖固定在稳定 v1.x：`mcp>=1.28.1,<2`。SDK v2 beta 不进入 V2 M4 稳定基线。

## Tool Allowlist

### `status`

- 参数：无。
- 返回：artifact 数量/类型、可用 topic、最新 as_of、tool 列表和只读边界。

### `catalog`

- 可选参数：`artifact_type`、`limit`。
- `artifact_type` 必须是项目 registry 中的类型。
- `limit` 必须为 1-200，默认 100。
- 不接受 path、glob、URL 或输出目录。

### `query`

- 必填参数：`topic`。
- 可选参数：`code`，只允许 fund topic 且必须是 6 位数字。
- topic：`market`、`fund`、`portfolio`、`news`、`history`、`quality`。
- 返回 Research Context。

### `ask`

- 必填参数：`question`，1-1000 字符。
- 返回 Research Answer。
- 交易、买卖、仓位、申购赎回、推荐、收益承诺或券商请求返回 `refused`，不会转为工具动作。

### `evidence`

- 参数规则与 `query` 相同。
- 返回 Evidence Bundle；每个 finding 至少引用一个 EvidenceRef。

## McpToolResult

每个成功调用返回：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `schema_version` | string | 固定为 `1.0`。 |
| `generated_at` | string | UTC ISO-8601 时间。 |
| `generator` | string | 固定为 `fund_agent`。 |
| `tool` | string | 五个 allowlisted tool 之一。 |
| `status` | string | `ok`、`partial`、`unavailable`、`answered`、`refused` 或 `unsupported`。 |
| `data` | object | 对应公开 service 的纯 JSON 结果。 |
| `warnings` | array | 结构化 warning。 |
| `metadata` | object | 必须包含 `read_only=true`，并标记主评分/主风险未改变。 |

可以把 tool result 写入临时 JSON 后校验：

```bash
python -m fund_agent.cli validate-contract --mcp-result /tmp/mcp-result.json
```

## Error Taxonomy

- `invalid_argument`
- `unsupported_tool`
- `artifact_unavailable`
- `timeout`
- `dependency_missing`
- `internal_error`

FastMCP 层将预期错误转换为 `ToolError`。返回消息只包含错误码和安全摘要，不包含 traceback、绝对路径、secret 或原始异常详情。

## Timeout / Audit

- 默认 timeout 10 秒；有效范围大于 0 且不超过 60 秒。
- 每次调用追加一行 JSONL audit，记录 tool、duration、status、error code、参数摘要和结果计数。
- question 只记录 SHA-256 和最长 160 字符的脱敏预览。
- 未知 tool/参数名不会原样落盘。
- token、password、API key、Bearer 和 Cookie 必须脱敏。

## 兼容性

- 下游忽略未知可选字段。
- 新增可选 metadata 属于 minor-compatible 扩展。
- 新增写工具、删除/重命名现有工具、改变参数语义或放宽路径权限需要 major contract 和安全评审。
- SDK transport 细节不属于业务 contract；客户端应依赖 tool schema 和 McpToolResult。

## 安全边界

- 不提供任意路径、通用文件系统、shell、URL fetch、配置写入或 scheduler 工具。
- 不修改 watchlist、portfolio、provider、主评分或主风险。
- 不输出买卖建议，不自动交易，不接券商，不承诺收益。
- prompt injection 只作为问题文本进入 M3 guardrail，不能注册新工具或改变系统边界。

## 示例

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-07-13T08:00:00+00:00",
  "generator": "fund_agent",
  "tool": "status",
  "status": "ok",
  "data": {
    "service": "ya-fundmind-research",
    "artifact_count": 12,
    "available_topics": ["market", "fund", "portfolio", "news", "history", "quality"],
    "tools": ["status", "catalog", "query", "ask", "evidence"]
  },
  "warnings": [],
  "metadata": {
    "read_only": true,
    "main_score_changed": false,
    "main_risk_changed": false
  }
}
```
