from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
GENERATOR = "fund_agent"

CORE_FIELDS = {
    "report": (
        "schema_version",
        "generated_at",
        "generator",
        "as_of",
        "data_quality_grade",
        "provider_health",
        "provider_warnings",
        "candidates",
        "valuations",
        "portfolio",
        "risk_issues",
        "snapshot_delta",
        "report_metadata",
    ),
    "trace": (
        "schema_version",
        "generated_at",
        "generator",
        "as_of",
        "providers",
    ),
    "snapshot": (
        "generated_at",
        "generator",
        "as_of",
        "candidates",
        "valuations",
        "portfolio",
        "provider_health",
        "data_quality_grade",
    ),
}


@dataclass(frozen=True)
class ContractValidationResult:
    path: Path
    contract_type: str
    ok: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContractValidationSummary:
    results: tuple[ContractValidationResult, ...]

    @property
    def ok(self) -> bool:
        return all(result.ok for result in self.results)


def validate_contract_file(path: Path | str, contract_type: str) -> ContractValidationResult:
    resolved_path = Path(path)
    errors: list[str] = []
    warnings: list[str] = []
    try:
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return ContractValidationResult(
            path=resolved_path,
            contract_type=contract_type,
            ok=False,
            errors=(f"JSON read failed: {exc}",),
        )
    if not isinstance(payload, dict):
        errors.append("JSON root must be an object")
        payload = {}
    if contract_type not in CORE_FIELDS:
        errors.append(f"Unknown contract type: {contract_type}")
        return ContractValidationResult(
            path=resolved_path,
            contract_type=contract_type,
            ok=False,
            errors=tuple(errors),
        )
    _validate_metadata(payload, contract_type, errors, warnings)
    required_fields = CORE_FIELDS[contract_type]
    if contract_type == "snapshot" and "schema_version" not in payload:
        required_fields = ("as_of", "candidates", "valuations")
    for field in required_fields:
        if field not in payload:
            if field in {"schema_version", "generated_at"} and any(field in item for item in errors):
                continue
            errors.append(f"Missing core field: {field}")
    _validate_shape(payload, contract_type, errors)
    return ContractValidationResult(
        path=resolved_path,
        contract_type=contract_type,
        ok=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def validate_output_dir(output_dir: Path | str) -> ContractValidationSummary:
    resolved_dir = Path(output_dir)
    candidates = [
        (resolved_dir / "fund_agent_report.json", "report"),
        (_latest_snapshot(resolved_dir), "snapshot"),
        (_latest_trace(resolved_dir), "trace"),
    ]
    results = [
        validate_contract_file(path, contract_type)
        for path, contract_type in candidates
        if path is not None and path.exists()
    ]
    return ContractValidationSummary(results=tuple(results))


def _validate_metadata(
    payload: dict[str, Any],
    contract_type: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    schema_version = payload.get("schema_version")
    if schema_version is None and contract_type == "snapshot":
        warnings.append("Legacy snapshot missing schema_version; accepted for compatibility.")
    elif schema_version is None:
        errors.append("Missing core field: schema_version")
    elif str(schema_version) != SCHEMA_VERSION:
        warnings.append(f"Unexpected schema_version {schema_version}; validator expects {SCHEMA_VERSION}.")
    if payload.get("generator") != GENERATOR and not (
        contract_type == "snapshot" and "schema_version" not in payload
    ):
        errors.append("Missing or invalid generator")
    if not payload.get("generated_at") and not (
        contract_type == "snapshot" and "schema_version" not in payload
    ):
        errors.append("Missing core field: generated_at")


def _validate_shape(payload: dict[str, Any], contract_type: str, errors: list[str]) -> None:
    list_fields = {
        "report": ("provider_health", "provider_warnings", "candidates", "risk_issues"),
        "trace": ("providers",),
    }
    dict_fields = {
        "report": ("valuations", "report_metadata"),
        "snapshot": ("candidates", "valuations"),
    }
    for field in list_fields.get(contract_type, ()):
        if field in payload and not isinstance(payload[field], list):
            errors.append(f"Field must be a list: {field}")
    for field in dict_fields.get(contract_type, ()):
        if field in payload and not isinstance(payload[field], dict):
            errors.append(f"Field must be an object: {field}")


def _latest_snapshot(output_dir: Path) -> Path | None:
    snapshot_dir = output_dir / "snapshots"
    if not snapshot_dir.exists():
        return None
    candidates = sorted(snapshot_dir.glob("*.json"))
    return candidates[-1] if candidates else None


def _latest_trace(output_dir: Path) -> Path | None:
    trace_dir = output_dir / "traces"
    if not trace_dir.exists():
        return None
    candidates = sorted(trace_dir.glob("provider-*.json"))
    return candidates[-1] if candidates else None
