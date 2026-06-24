# JSON Report Contract v1

## Schema Version

- `schema_version`: `"1.0"`
- `generator`: `"fund_agent"`
- Default path: `outputs/fund_agent_report.json`

## Purpose

The JSON report is the primary machine-readable research output for downstream Agent, Skill, Web, or batch consumers. It mirrors the Markdown/HTML report at a structured level so consumers do not need to parse Markdown.

## Required Fields

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | Contract version. Current value is `"1.0"`. |
| `generated_at` | string | UTC ISO-8601 timestamp when the JSON report was generated. |
| `generator` | string | Output producer. Current value is `"fund_agent"`. |
| `as_of` | string | Report date in `YYYY-MM-DD` form when provided by CLI. |
| `data_quality_grade` | string | Overall grade: `normal`, `warning`, or `degraded`. |
| `provider_health` | array | Structured provider health records. |
| `provider_warnings` | array | Flattened provider warnings across providers. |
| `candidates` | array | Ranked research candidates. |
| `valuations` | object | Valuation results keyed by fund code. |
| `portfolio` | object or null | Portfolio summary when holdings are provided. |
| `risk_issues` | array | Portfolio/data-quality risk issues. |
| `snapshot_delta` | object or null | Comparison against the previous snapshot. |
| `report_metadata` | object | Report format metadata and disclaimer. |

## Optional Fields

Consumers must treat unknown fields as optional extension fields. Future minor versions may add optional fields at the top level or inside nested objects.

## Field Notes

- `provider_health` uses the provider health shape documented in `provider-trace-v1.md`.
- `valuations` keys are normalized fund codes.
- `portfolio` is `null` for screen-only flows or when no holdings config is available.
- `snapshot_delta` is `null` when no previous snapshot exists.
- `risk_issues` may be empty even when `data_quality_grade` is not `normal`; consumers should read both.

## Compatibility

- v1 readers should require the top-level metadata fields and core sections listed above.
- Unknown fields must be ignored.
- Missing optional nested fields should not crash readers.
- Do not infer schema from Markdown/HTML.

## Downstream Reading Guidance

- Read `fund_agent_report.json` directly with a JSON parser.
- Use `schema_version` before relying on field semantics.
- Use `data_quality_grade` and `provider_warnings` to decide whether automated downstream actions need manual review.
- Treat this output as research support only. It is not a trading instruction.

## Example

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-06-23T09:28:18.079372+00:00",
  "generator": "fund_agent",
  "as_of": "2026-06-23",
  "data_quality_grade": "normal",
  "provider_health": [],
  "provider_warnings": [],
  "candidates": [
    {
      "code": "510300",
      "name": "沪深300ETF",
      "category": "ETF",
      "score": 8.2
    }
  ],
  "valuations": {
    "510300": {
      "code": "510300",
      "method": "nav_based",
      "confidence": "High"
    }
  },
  "portfolio": null,
  "risk_issues": [],
  "snapshot_delta": null,
  "report_metadata": {
    "format": "fund_agent_report_json",
    "schema_version": "1.0"
  }
}
```
