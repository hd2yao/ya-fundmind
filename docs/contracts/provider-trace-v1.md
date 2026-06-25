# Provider Trace Contract v1

## Schema Version

- `schema_version`: `"1.0"`
- `generator`: `"fund_agent"`
- Default path: `outputs/traces/provider-YYYY-MM-DD.json`

## Purpose

The provider trace records data-source execution details for debugging, audit, and data-quality analysis. It is more operational than the JSON report and should be used to inspect provider fetch, mapping, cache, fallback, and warning behavior.

## Required Fields

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | Contract version. Current value is `"1.0"`. |
| `generated_at` | string | UTC ISO-8601 timestamp when the trace file was generated. |
| `generator` | string | Output producer. Current value is `"fund_agent"`. |
| `as_of` | string | Report date. |
| `providers` | array | Provider health records. |

Each provider record should include:

| Field | Type | Meaning |
| --- | --- | --- |
| `provider` | string | Provider name, for example `fixture` or `akshare`. |
| `provider_version` | string or null | Provider library version when known. |
| `started_at` / `finished_at` | string | Provider execution timestamps. |
| `duration_ms` | number | Provider execution duration. |
| `live_row_count` | number | Raw rows returned by live endpoints. |
| `mapped_row_count` | number | Rows mapped into normalized fund records. |
| `skipped_row_count` | number | Rows skipped during mapping. |
| `cache_write_count` | number | Records written to SQLite cache. |
| `fallback_used` | boolean | Whether cache fallback was used. |
| `fallback_reason` | string or null | Reason for fallback. |
| `fallback_source` | string or null | Fallback source, usually `cache`. |
| `watchlist_requested_count` | number | Watchlist codes requested. |
| `watchlist_matched_count` | number | Watchlist codes matched. |
| `watchlist_missing_codes` | array | Watchlist codes missing from provider data. |
| `warnings` | array | Provider warnings with `code`, `message`, `severity`, and optional `details`. |
| `endpoints` | array | Endpoint-level traces. |

Endpoint records include `endpoint`, `started_at`, `finished_at`, `duration_ms`, `attempts`, `success`, `error`, `timeout_seconds`, `live_row_count`, `mapped_row_count`, and `skipped_row_count`.

## Optional Fields

Future versions may add provider-specific metadata. Consumers should ignore unknown fields and must not assume every provider has endpoint traces. Fixture provider traces may have an empty `endpoints` array.

Current v1 optional Tiantian enrichment fields may include:

- `cache_read_count`
- `windows_requested`
- `windows_generated`

These fields are diagnostic extensions for explicit Tiantian enrichment and cache fallback. Consumers must not require them for all providers.

## Compatibility

- v1 readers should require the top-level metadata and `providers`.
- Missing endpoint entries are valid when a provider has no live endpoint.
- Unknown warning codes should be displayed or logged, not rejected.
- Trace files are operational artifacts and may be pruned by retention policy.

## Downstream Reading Guidance

- Use trace files for diagnostics, not final investment output.
- Use `fallback_used`, `warnings`, and `watchlist_missing_codes` to decide whether report data needs manual review.
- Do not parse CLI stdout or Markdown to reconstruct provider health.

## Example

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-06-23T09:28:18.079720+00:00",
  "generator": "fund_agent",
  "as_of": "2026-06-23",
  "providers": [
    {
      "provider": "akshare",
      "provider_version": "1.17.0",
      "live_row_count": 100,
      "mapped_row_count": 98,
      "skipped_row_count": 2,
      "cache_write_count": 98,
      "fallback_used": false,
      "warnings": [],
      "endpoints": [
        {
          "endpoint": "fund_open_fund_rank_em",
          "attempts": 1,
          "success": true,
          "timeout_seconds": 20
        }
      ]
    }
  ]
}
```
