# Evidence Bundle Contract v1

## Schema Version

- `schema_version`: `"1.0"`
- `generator`: `"fund_agent"`
- 默认路径：`outputs/evidence/research_evidence.json`

## 文件用途

Evidence Bundle 把 Research Context 中的关键研究事实转换为可追溯 finding。每个 finding 至少引用一个 EvidenceRef，EvidenceRef 必须定位到原始白名单 JSON artifact 和有效 JSON Pointer。

它用于后续 Research Copilot、Skill、MCP、Web 和人工审核。下游不应解析 Markdown/HTML，也不应把 bundle 当作买卖建议或交易指令。

## 必填字段

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `schema_version` | string | 当前 contract 版本，固定为 `1.0`。 |
| `generated_at` | string | UTC ISO-8601 生成时间。 |
| `generator` | string | 固定为 `fund_agent`。 |
| `topic` | string | `market`、`fund`、`portfolio`、`news`、`history` 或 `quality`。 |
| `status` | string | `ok`、`partial` 或 `unavailable`。 |
| `as_of` | string/null | 来源 context 的最新日期。 |
| `code` | string/null | fund 查询代码。 |
| `quality_grade` | string | `normal`、`unknown`、`warning`、`degraded` 或 `blocked`。 |
| `review_required` | boolean | 是否必须人工审核。 |
| `findings` | array | 结构化研究 finding。 |
| `evidence` | array | EvidenceRef 列表。 |
| `data_gaps` | array | 无法从原 artifact 定位的预期字段。 |
| `warnings` | array | 质量、加载、冲突和兼容 warning。 |
| `metadata` | object | 计数、来源 context 版本和研究边界。 |

## EvidenceRef

每个 EvidenceRef 包含：

- `evidence_id`：由 artifact id、JSON Pointer 和 claim type 稳定生成。
- `artifact_id`
- `artifact_type`
- `path`：相对 `output_dir` 的白名单路径。
- `json_pointer`：RFC 6901 pointer。
- `claim_type`
- `as_of`
- `source`
- `quality_grade`
- `stale`
- `value`：pointer 定位的原始结构化值。
- `excerpt`：最长 240 字符的必要短摘录。
- `metadata`

`value` 必须与重新读取 `path` 后解析 `json_pointer` 的结果一致。

## ResearchFinding

每个 finding 包含：

- `finding_id`
- `topic`
- `category`
- `label`
- `value`
- `code`
- `quality_grade`
- `evidence_ids`：至少一个，且必须存在于本 bundle 的 `evidence`。
- `review_required`
- `warnings`
- `metadata.claim_type`

没有 EvidenceRef 时不得生成 finding。缺失字段进入 `data_gaps`。

## 质量规则

- `normal`：证据存在，未发现质量问题。
- `warning`：fallback、普通 provider warning、legacy schema、样本不足或 data gap。
- `degraded`：stale、artifact degraded 或跨来源冲突。
- `blocked`：critical provider warning、loader blocked 或完全没有 finding/evidence。

只有实际被 finding 引用的 artifact 参与 bundle 质量聚合；未使用的旧历史 artifact 不应污染最新 finding 的质量。

`degraded`、`blocked` 或来源冲突必须设置 `review_required=true`。普通 warning 可以由下游选择人工复核，但本 contract 不强制。

## 冲突规则

只在以下条件同时满足时标记冲突：

- `claim_type` 和实体 code 相同；
- 至少两个不同已知 source；
- 结构化值不同。

相同来源的历史变化不算来源冲突；不同来源给出相同值也不算冲突。冲突 warning 格式为 `evidence_conflict:<claim_type>`。

## 状态和 Exit Code

- `ok`：有 finding，context 和 evidence 完整，CLI exit 0。
- `partial`：仍有 finding，但存在 context partial、data gap、加载 warning 或冲突，CLI exit 0。
- `unavailable`：没有可用 finding/evidence，CLI 写 bundle 后 exit 1。
- 输入 Research Context contract 无效：不写 bundle，exit 2。

## 兼容性说明

- 未知字段必须忽略。
- 新增可选 finding/evidence metadata 属于 minor-compatible 扩展。
- 删除、重命名、重定类型或改变 required 字段语义需要 major contract 版本。
- 旧 V1 artifact 可以通过 M1 loader 安全降级，但会保留 warning。

## 下游读取建议

- 先检查 `status`、`quality_grade` 和 `review_required`。
- 使用 `finding.evidence_ids` 连接 EvidenceRef，不依赖数组顺序。
- 在展示关键 finding 时提供 artifact path、as_of、source 和 quality。
- `blocked` finding 不应进入自动化解释结论。
- 不得根据空 `data_gaps` 之外的缺失字段自行猜测值。

## 示例

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-07-13T04:00:00+00:00",
  "generator": "fund_agent",
  "topic": "market",
  "status": "ok",
  "as_of": "2026-07-12",
  "code": null,
  "quality_grade": "normal",
  "review_required": false,
  "findings": [
    {
      "finding_id": "finding-...",
      "topic": "market",
      "category": "breadth",
      "label": "基金总数",
      "value": 21488,
      "code": null,
      "quality_grade": "normal",
      "evidence_ids": ["evidence-..."],
      "review_required": false,
      "warnings": [],
      "metadata": {"claim_type": "market.total_funds"}
    }
  ],
  "evidence": [
    {
      "evidence_id": "evidence-...",
      "artifact_id": "artifact-...",
      "artifact_type": "market_intelligence",
      "path": "market/market_intelligence_report.json",
      "json_pointer": "/total_funds",
      "claim_type": "market.total_funds",
      "as_of": "2026-07-12",
      "source": "akshare",
      "quality_grade": "normal",
      "stale": false,
      "value": 21488,
      "excerpt": "21488",
      "metadata": {}
    }
  ],
  "data_gaps": [],
  "warnings": [],
  "metadata": {
    "finding_count": 1,
    "evidence_count": 1,
    "not_production_model": true,
    "main_score_changed": false,
    "main_risk_changed": false
  }
}
```
