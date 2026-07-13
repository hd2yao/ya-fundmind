# Research Context Contract v1

## Schema Version

- `schema_version`: `"1.0"`
- `generator`: `"fund_agent"`
- 默认路径：`outputs/research_queries/research_context.json`

## 文件用途

Research Context 是 V2 的统一只读查询输出。它从 V1 JSON artifact 中提取与指定 topic 相关的紧凑结构化上下文，供后续 Evidence、Copilot、Skill、MCP 和 Web 使用。

下游不应解析 Markdown/HTML，也不应绕过 Artifact Catalog 任意读取本地文件。

## 必填字段

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `schema_version` | string | 当前 contract 版本，固定为 `1.0`。 |
| `generated_at` | string | UTC ISO-8601 生成时间。 |
| `generator` | string | 生成器，固定为 `fund_agent`。 |
| `topic` | string | `market`、`fund`、`portfolio`、`news`、`history` 或 `quality`。 |
| `status` | string | `ok`、`partial` 或 `unavailable`。 |
| `as_of` | string/null | 本次上下文所引用 artifact 的最新日期。 |
| `code` | string/null | fund 查询的标准化基金代码；其他 topic 通常为 null。 |
| `artifacts` | array | 本次查询涉及的 ArtifactDescriptor。 |
| `data` | object | topic 对应的紧凑结构化数据。 |
| `warnings` | array | 缺失、损坏、旧 schema 或选择问题。 |
| `metadata` | object | 查询行为元数据。 |

## ArtifactDescriptor

每个 `artifacts` 项至少可能包含：

- `artifact_id`
- `artifact_type`
- `path`：相对 `output_dir` 的白名单路径
- `schema_version`
- `as_of`
- `generated_at`
- `source`
- `quality_grade`
- `stale`
- `content_hash`
- `warnings`
- `metadata`

字段值可能为 null，但下游不得自行猜测缺失值。

## Topic Data

### market

包含 `market_intelligence`、`market_trend` 和可选 `theme_rankings`。为控制体积，不包含全量 `records` 和 `classifications`。

### fund

传 `--code` 时包含目标 `fund` 和 `coverage_summary`；未传 code 时包含 `funds` 和 coverage。没有匹配时 status 为 partial，并出现 `fund_not_found:<code>`。

### portfolio

包含 `portfolio` report。

### news

包含 `news` evidence report。

### history

包含 compact `timeline` 和最新 `latest_delta`，不复制所有历史 snapshot payload。

### quality

包含 report、provider trace、ops、daily research 和 long-horizon 的质量/readiness 摘要。

## 状态和 Exit Code

- `ok`：核心数据完整，CLI exit 0。
- `partial`：部分 artifact 不可用或目标缺失，但仍有可用上下文，CLI exit 0。
- `unavailable`：没有可用 artifact，CLI 仍写 JSON，exit 1。
- 参数或基金代码错误：不写输出，exit 2。

## 兼容性说明

- 未知字段必须忽略。
- 缺少 `schema_version` 的旧 artifact 可以读取，但 context warnings 会包含 `schema_version_missing`。
- 单个 artifact 损坏时其他 artifact 继续返回。
- 新增可选 topic 字段属于 minor-compatible 扩展。
- 删除、重命名、重定类型或改变现有字段语义需要 major contract 版本。

## 下游读取建议

- 先检查 `status`、`warnings` 和每个 artifact 的 `quality_grade/stale`。
- 使用 `artifact_id` 和 `path` 做后续证据定位，不依赖数组顺序。
- 不把 Research Context 当作投资建议或交易指令。
- M2 Evidence 层会增加 JSON Pointer 引用；M1 下游不应自行拼接自然语言结论。

## 示例

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-07-13T03:00:00+00:00",
  "generator": "fund_agent",
  "topic": "market",
  "status": "ok",
  "as_of": "2026-07-12",
  "code": null,
  "artifacts": [
    {
      "artifact_id": "artifact-0123456789abcdef0123",
      "artifact_type": "market_intelligence",
      "path": "market/market_intelligence_report.json",
      "schema_version": "1.0",
      "as_of": "2026-07-12",
      "generated_at": "2026-07-12T14:00:00+00:00",
      "source": "akshare",
      "quality_grade": null,
      "stale": false,
      "content_hash": "...",
      "warnings": [],
      "metadata": {}
    }
  ],
  "data": {
    "market_intelligence": {
      "total_funds": 21488,
      "total_etfs": 3517,
      "top_themes": []
    }
  },
  "warnings": [],
  "metadata": {
    "compact": true,
    "full_payloads_embedded": false
  }
}
```
