# Research Answer Contract v1

## Schema Version

- `schema_version`: `"1.0"`
- `generator`: `"fund_agent"`
- 默认 JSON：`outputs/copilot/research_answer.json`
- 默认 Markdown：`outputs/copilot/research_answer.md`
- 默认审计：`outputs/audit/research_queries.jsonl`

## 文件用途

Research Answer 是只读 Research Copilot 的机器可读回答。它把受支持的问题映射到 Research Context 和 Evidence Bundle，并原样保留 finding、evidence、数据缺口和质量信息。下游应读取本 JSON，不应解析 Markdown。

该文件仅用于研究辅助和人工审核，不是生产评分模型，不修改主评分或主风险，不构成买卖建议，不承诺收益，也不能触发交易。

## 必填字段

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `schema_version` | string | 当前固定为 `1.0`。 |
| `generated_at` | string | UTC ISO-8601 生成时间。 |
| `generator` | string | 固定为 `fund_agent`。 |
| `question` | string | 规范化后的用户问题。 |
| `intent` | object | intent、code、confidence、blocked、reason 和规范化问题。 |
| `answer_status` | string | `answered`、`partial`、`unavailable`、`refused` 或 `unsupported`。 |
| `as_of` | string/null | 证据对应的数据日期。 |
| `summary` | string | 由确定性模板生成的状态摘要，不新增事实数值。 |
| `findings` | array | 从 Evidence Bundle 原样复制的证据化发现。 |
| `evidence` | array | 从 Evidence Bundle 原样复制的 EvidenceRef。 |
| `data_gaps` | array | 缺失数据、缺少基金代码或主题产物不可用。 |
| `warnings` | array | 数据质量、加载和边界 warning。 |
| `review_required` | boolean | 是否需要人工复核。 |
| `confidence` | string | `high`、`medium` 或 `low`。 |
| `blocked_reason` | string/null | 拒绝请求的结构化原因。 |
| `not_investment_advice` | boolean | 必须为 `true`。 |
| `metadata` | object | 只读 plan、质量和主模型未改变标记。 |

## Intent 和状态

支持的研究 intent 是 `market`、`fund`、`portfolio`、`news`、`history` 和 `quality`。`blocked_transaction` 用于交易、仓位、收益承诺或推荐请求；`unsupported` 用于当前研究范围之外的问题。

- `answered`：有完整 evidence-backed findings，CLI exit 0。
- `partial`：仍有部分 finding，或基金问题缺少明确代码，CLI exit 0。
- `unavailable`：没有可读取 artifact 或无法建立证据，CLI exit 1。
- `refused`：请求越过只读研究边界，必须有 `blocked_reason`，CLI exit 1。
- `unsupported`：问题不属于支持的研究主题，CLI exit 1。

## 引用约束

- 每个 finding 必须至少引用一个本文件中存在的 `evidence_id`。
- Copilot 不得改写 Evidence Bundle 中的 finding 数值、evidence、质量等级或引用路径。
- 没有证据的字段必须进入 `data_gaps`，不能生成肯定结论。
- `degraded`、`blocked` 或冲突 evidence 应保留 `review_required=true`。
- Markdown renderer 只能展示本 JSON 中已有字段。

## Optional Renderer

默认 renderer 不依赖 LLM。可选 renderer 只接收 Research Answer 的 JSON 深拷贝并返回文本；它不能修改或覆盖 JSON answer。可选 renderer 失败时回退到确定性 Markdown。

## Audit

审计采用 append-only JSONL，记录时间、问题 SHA-256、脱敏预览、intent、状态、finding/evidence/data gap/warning 数量和输出路径。审计不得保存完整原问题，也不得保存 token、password、API key、Cookie 或其他 secret。

## 兼容性

- 下游必须忽略未知字段。
- 新增可选 metadata 或展示字段属于 minor-compatible 扩展。
- 删除、重命名、改变必填字段类型或语义需要 major contract 版本。
- V1 report、snapshot、trace 和 M1/M2 contract 保持不变。

## 下游读取建议

1. 先检查 `answer_status`、`confidence` 和 `review_required`。
2. 使用 `finding.evidence_ids` 连接 EvidenceRef，不依赖数组顺序。
3. 展示来源时同时展示 `source`、`as_of`、`path`、`json_pointer` 和质量等级。
4. `refused`、`unsupported`、`unavailable` 不应被转换为研究结论。
5. 不解析 Markdown，不根据缺失字段补写数值，不执行任何写配置或交易行为。

## 示例

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-07-13T08:00:00+00:00",
  "generator": "fund_agent",
  "question": "今天市场有什么变化？",
  "intent": {
    "intent": "market",
    "code": null,
    "confidence": "high",
    "blocked": false,
    "reason": null,
    "normalized_question": "今天市场有什么变化？"
  },
  "answer_status": "answered",
  "as_of": "2026-07-13",
  "summary": "已基于 9 条可追溯证据整理 9 项研究发现。",
  "findings": [
    {
      "finding_id": "finding-...",
      "label": "基金总数",
      "value": 21488,
      "quality_grade": "normal",
      "evidence_ids": ["evidence-..."]
    }
  ],
  "evidence": [
    {
      "evidence_id": "evidence-...",
      "source": "akshare",
      "path": "market/market_intelligence_report.json",
      "json_pointer": "/total_funds"
    }
  ],
  "data_gaps": [],
  "warnings": [],
  "review_required": false,
  "confidence": "high",
  "blocked_reason": null,
  "not_investment_advice": true,
  "metadata": {
    "read_only": true,
    "main_score_changed": false,
    "main_risk_changed": false
  }
}
```
