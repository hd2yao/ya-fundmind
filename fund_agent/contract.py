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
    "research_context": (
        "schema_version",
        "generated_at",
        "generator",
        "topic",
        "status",
        "as_of",
        "code",
        "artifacts",
        "data",
        "warnings",
        "metadata",
    ),
    "evidence_bundle": (
        "schema_version",
        "generated_at",
        "generator",
        "topic",
        "status",
        "as_of",
        "code",
        "quality_grade",
        "review_required",
        "findings",
        "evidence",
        "data_gaps",
        "warnings",
        "metadata",
    ),
    "research_answer": (
        "schema_version",
        "generated_at",
        "generator",
        "question",
        "intent",
        "answer_status",
        "as_of",
        "summary",
        "findings",
        "evidence",
        "data_gaps",
        "warnings",
        "review_required",
        "confidence",
        "blocked_reason",
        "not_investment_advice",
        "metadata",
    ),
    "mcp_tool_result": (
        "schema_version",
        "generated_at",
        "generator",
        "tool",
        "status",
        "data",
        "warnings",
        "metadata",
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
    if contract_type == "research_context":
        _validate_research_context_values(payload, errors)
    elif contract_type == "evidence_bundle":
        _validate_evidence_bundle_values(payload, errors)
    elif contract_type == "research_answer":
        _validate_research_answer_values(payload, errors)
    elif contract_type == "mcp_tool_result":
        _validate_mcp_tool_result_values(payload, errors)
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
        (resolved_dir / "research_queries" / "research_context.json", "research_context"),
        (resolved_dir / "evidence" / "research_evidence.json", "evidence_bundle"),
        (resolved_dir / "copilot" / "research_answer.json", "research_answer"),
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
        "research_context": ("artifacts", "warnings"),
        "evidence_bundle": ("findings", "evidence", "data_gaps", "warnings"),
        "research_answer": ("findings", "evidence", "data_gaps", "warnings"),
        "mcp_tool_result": ("warnings",),
    }
    dict_fields = {
        "report": ("valuations", "report_metadata"),
        "snapshot": ("candidates", "valuations"),
        "research_context": ("data", "metadata"),
        "evidence_bundle": ("metadata",),
        "research_answer": ("intent", "metadata"),
        "mcp_tool_result": ("data", "metadata"),
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


def _validate_research_context_values(payload: dict[str, Any], errors: list[str]) -> None:
    topic = payload.get("topic")
    if topic not in {"market", "fund", "portfolio", "news", "history", "quality"}:
        errors.append(f"Unsupported research topic: {topic}")
    status = payload.get("status")
    if status not in {"ok", "partial", "unavailable"}:
        errors.append(f"Unsupported research context status: {status}")
    code = payload.get("code")
    if code is not None and not isinstance(code, str):
        errors.append("Field must be a string or null: code")


def _validate_evidence_bundle_values(payload: dict[str, Any], errors: list[str]) -> None:
    topic = payload.get("topic")
    if topic not in {"market", "fund", "portfolio", "news", "history", "quality"}:
        errors.append(f"Unsupported evidence topic: {topic}")
    status = payload.get("status")
    if status not in {"ok", "partial", "unavailable"}:
        errors.append(f"Unsupported evidence bundle status: {status}")
    grade = payload.get("quality_grade")
    if grade not in {"normal", "unknown", "warning", "degraded", "blocked"}:
        errors.append(f"Unsupported evidence quality grade: {grade}")
    if "review_required" in payload and not isinstance(payload["review_required"], bool):
        errors.append("Field must be a boolean: review_required")

    evidence_items = payload.get("evidence")
    findings = payload.get("findings")
    if not isinstance(evidence_items, list) or not isinstance(findings, list):
        return
    evidence_ids: set[str] = set()
    for index, item in enumerate(evidence_items):
        if not isinstance(item, dict):
            errors.append(f"Evidence item must be an object: {index}")
            continue
        for field in (
            "evidence_id",
            "artifact_id",
            "artifact_type",
            "path",
            "content_hash",
            "json_pointer",
            "claim_type",
            "as_of",
            "source",
            "quality_grade",
            "stale",
            "value",
            "excerpt",
            "metadata",
        ):
            if field not in item:
                errors.append(f"Evidence item missing field: {field}")
        evidence_id = item.get("evidence_id")
        if isinstance(evidence_id, str):
            if evidence_id in evidence_ids:
                errors.append(f"Duplicate evidence id: {evidence_id}")
            evidence_ids.add(evidence_id)
    for index, item in enumerate(findings):
        if not isinstance(item, dict):
            errors.append(f"Finding must be an object: {index}")
            continue
        finding_id = str(item.get("finding_id") or index)
        for field in (
            "finding_id",
            "topic",
            "category",
            "label",
            "value",
            "code",
            "quality_grade",
            "evidence_ids",
            "review_required",
            "warnings",
            "metadata",
        ):
            if field not in item:
                errors.append(f"Finding missing field: {field}")
        references = item.get("evidence_ids")
        if not isinstance(references, list) or not references:
            errors.append(f"Finding must reference at least one evidence id: {finding_id}")
            continue
        for evidence_id in references:
            if evidence_id not in evidence_ids:
                errors.append(f"Finding references unknown evidence id: {evidence_id}")


def _validate_research_answer_values(payload: dict[str, Any], errors: list[str]) -> None:
    status = payload.get("answer_status")
    if status not in {"answered", "partial", "unavailable", "refused", "unsupported"}:
        errors.append(f"Unsupported research answer status: {status}")
    confidence = payload.get("confidence")
    if confidence not in {"high", "medium", "low"}:
        errors.append(f"Unsupported research answer confidence: {confidence}")
    intent = payload.get("intent")
    if isinstance(intent, dict):
        intent_name = intent.get("intent")
        if intent_name not in {
            "market",
            "fund",
            "portfolio",
            "news",
            "history",
            "quality",
            "blocked_transaction",
            "unsupported",
        }:
            errors.append(f"Unsupported research answer intent: {intent_name}")
    if "review_required" in payload and not isinstance(payload["review_required"], bool):
        errors.append("Field must be a boolean: review_required")
    if payload.get("not_investment_advice") is not True:
        errors.append("Field must be true: not_investment_advice")
    if status == "refused" and not payload.get("blocked_reason"):
        errors.append("Refused answer must include blocked_reason")

    evidence_items = payload.get("evidence")
    findings = payload.get("findings")
    if not isinstance(evidence_items, list) or not isinstance(findings, list):
        return
    evidence_ids = {
        item.get("evidence_id")
        for item in evidence_items
        if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)
    }
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            errors.append(f"Finding must be an object: {index}")
            continue
        finding_id = str(finding.get("finding_id") or index)
        references = finding.get("evidence_ids")
        if not isinstance(references, list) or not references:
            errors.append(f"Finding must reference at least one evidence id: {finding_id}")
            continue
        for evidence_id in references:
            if evidence_id not in evidence_ids:
                errors.append(f"Finding references unknown evidence id: {evidence_id}")


def _validate_mcp_tool_result_values(payload: dict[str, Any], errors: list[str]) -> None:
    tool = payload.get("tool")
    if tool not in {"status", "catalog", "query", "ask", "evidence"}:
        errors.append(f"Unsupported MCP tool: {tool}")
    status = payload.get("status")
    if status not in {
        "ok",
        "partial",
        "unavailable",
        "answered",
        "refused",
        "unsupported",
    }:
        errors.append(f"Unsupported MCP tool result status: {status}")
    metadata = payload.get("metadata")
    if isinstance(metadata, dict) and metadata.get("read_only") is not True:
        errors.append("MCP tool result metadata.read_only must be true")


def _latest_trace(output_dir: Path) -> Path | None:
    trace_dir = output_dir / "traces"
    if not trace_dir.exists():
        return None
    candidates = sorted(trace_dir.glob("provider-*.json"))
    return candidates[-1] if candidates else None
