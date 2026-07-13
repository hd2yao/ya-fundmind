# Schema Versioning Policy

## Current Version

Current machine-readable output contracts use `schema_version: "1.0"`.

Covered files:

- `outputs/fund_agent_report.json`
- `outputs/traces/provider-YYYY-MM-DD.json`
- `outputs/snapshots/YYYY-MM-DD.json`
- `outputs/research_queries/research_context.json`
- `outputs/evidence/research_evidence.json`

## Version Semantics

Version numbers use `major.minor` in contract fields and may be discussed with patch-level change notes in documentation.

### Patch Changes

Patch changes fix bugs without changing field names, field types, or field semantics.

Examples:

- Correcting a typo in documentation.
- Fixing a validator bug that incorrectly rejected a valid v1 file.
- Fixing generated timestamps while preserving the same field meaning.

### Minor Changes

Minor changes may add optional fields while preserving existing fields and meanings.

Examples:

- Adding a new optional top-level metadata field.
- Adding a new optional provider warning detail.
- Adding a new optional nested section for downstream diagnostics.

Downstream readers must ignore unknown fields so minor versions remain compatible.

### Major Changes

Major changes are required when existing fields are deleted, renamed, retyped, or given different semantics.

Examples:

- Renaming `data_quality_grade`.
- Changing `provider_health` from an array to an object.
- Removing `valuations`.
- Changing a score scale without a new field name.

## Legacy Compatibility

- Old snapshots may lack `schema_version`, `generated_at`, `generator`, `provider_health`, or `data_quality_grade`.
- Validators should warn on legacy snapshots instead of crashing when the legacy core fields are present.
- Old traces and reports without schema metadata are not considered v1 contract files.
- Historical comparison code should treat missing fields as unknown or empty when possible.

## Downstream Reader Rules

- Always parse JSON directly.
- Do not parse Markdown or HTML for machine data.
- Check `schema_version` before relying on field semantics.
- Ignore unknown fields.
- Treat missing optional fields as empty or unknown.
- Fail loudly on missing required fields for current report and trace files.
- Treat validation warnings as review signals, not hard failures, unless the caller chooses a stricter policy.

## Validation Command

Validate all known outputs in a directory:

```bash
python -m fund_agent.cli validate-contract --output-dir outputs
```

Validate individual files:

```bash
python -m fund_agent.cli validate-contract --report outputs/fund_agent_report.json
python -m fund_agent.cli validate-contract --trace outputs/traces/provider-2026-06-23.json
python -m fund_agent.cli validate-contract --snapshot outputs/snapshots/2026-06-23.json
python -m fund_agent.cli validate-contract --research-context outputs/research_queries/research_context.json
python -m fund_agent.cli validate-contract --evidence-bundle outputs/evidence/research_evidence.json
```
