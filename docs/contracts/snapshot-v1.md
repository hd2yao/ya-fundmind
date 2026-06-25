# Snapshot Contract v1

## Schema Version

- `schema_version`: `"1.0"`
- `generator`: `"fund_agent"`
- Default path: `outputs/snapshots/YYYY-MM-DD.json`

## Purpose

Snapshots store one run's compact machine-readable state for historical comparison. They are used to calculate score changes, valuation changes, risk changes, holding-risk changes, data-quality changes, and provider-health deltas.

## Required Fields

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | Contract version. Current value is `"1.0"`. |
| `generated_at` | string | UTC ISO-8601 timestamp when the snapshot was generated. |
| `generator` | string | Output producer. Current value is `"fund_agent"`. |
| `as_of` | string | Snapshot date. |
| `candidates` | object | Candidate scores keyed by fund code. |
| `valuations` | object | Valuation summaries keyed by fund code. |
| `portfolio` | object or null | Portfolio summary and position state. |
| `provider_health` | array | Provider health records for the run. |
| `data_quality_grade` | string | Overall data-quality grade for the run. |

## Optional Fields

- Future versions may add new delta inputs.
- Nested provider health may omit provider-specific fields.
- Legacy snapshots before v1 may lack `schema_version`, `generated_at`, `generator`, `provider_health`, or `data_quality_grade`.
- `signal_quality_summary` may be present when signal candidate experiments are generated. It is optional and must not be required by v1 readers.

## Field Notes

- `candidates` values include `code`, `name`, `score`, and `evidence_label`.
- `valuations` values include `code`, `method`, `estimated_value`, and `confidence`.
- `portfolio.risk_issues` is used by historical risk comparison.
- `provider_health` follows the same shape used by provider trace.

## Compatibility

- Current validators accept legacy snapshots without `schema_version` as warnings when the legacy core fields exist.
- Compare logic must tolerate missing `provider_health` and missing data-quality fields.
- New snapshot fields should be additive in minor versions.

## Downstream Reading Guidance

- Use snapshots for historical comparison and state tracking.
- Do not use snapshots as the main report payload; use `fund_agent_report.json` for current report consumption.
- Ignore unknown fields.
- Do not parse Markdown to infer historical state.

## Example

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-06-23T09:28:18.079557+00:00",
  "generator": "fund_agent",
  "as_of": "2026-06-23",
  "candidates": {
    "510300": {
      "code": "510300",
      "name": "沪深300ETF",
      "score": 8.2,
      "evidence_label": "strong"
    }
  },
  "valuations": {
    "510300": {
      "code": "510300",
      "method": "nav_based",
      "estimated_value": 5.01,
      "confidence": "High"
    }
  },
  "portfolio": null,
  "provider_health": [],
  "data_quality_grade": "normal"
}
```
