from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
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
    "release_readiness": (
        "schema_version",
        "generated_at",
        "generator",
        "release_target",
        "observation_mode",
        "required_provenance",
        "status",
        "minimum_valid_runs",
        "valid_run_count",
        "observed_run_dates",
        "run_observations",
        "contract_summary",
        "performance",
        "boundaries",
        "blockers",
        "warnings",
    ),
    "fund_profile": (
        "schema_version",
        "generated_at",
        "generator",
        "code",
        "as_of",
        "catalog",
        "profile",
        "trading_rule",
        "fees",
        "data_status",
        "profile_status",
        "trading_status",
        "fee_status",
        "not_production_model",
        "main_score_changed",
        "main_risk_changed",
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


def validate_contract_file(
    path: Path | str,
    contract_type: str,
    *,
    strict: bool = False,
) -> ContractValidationResult:
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
    _validate_metadata(payload, contract_type, errors, warnings, strict=strict)
    required_fields = CORE_FIELDS[contract_type]
    if contract_type == "snapshot" and "schema_version" not in payload and not strict:
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
    elif contract_type == "release_readiness":
        _validate_release_readiness_values(payload, errors)
    elif contract_type == "fund_profile":
        _validate_fund_profile_values(payload, errors)
    return ContractValidationResult(
        path=resolved_path,
        contract_type=contract_type,
        ok=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def validate_output_dir(
    output_dir: Path | str,
    *,
    strict: bool = False,
) -> ContractValidationSummary:
    resolved_dir = Path(output_dir)
    candidates = [
        (resolved_dir / "fund_agent_report.json", "report"),
        (_latest_snapshot(resolved_dir), "snapshot"),
        (_latest_trace(resolved_dir), "trace"),
        (resolved_dir / "research_queries" / "research_context.json", "research_context"),
        (resolved_dir / "evidence" / "research_evidence.json", "evidence_bundle"),
        (resolved_dir / "copilot" / "research_answer.json", "research_answer"),
        (resolved_dir / "release" / "v2_release_readiness.json", "release_readiness"),
        (_latest_fund_profile(resolved_dir), "fund_profile"),
    ]
    results = [
        validate_contract_file(path, contract_type, strict=strict)
        for path, contract_type in candidates
        if path is not None and path.exists()
    ]
    return ContractValidationSummary(results=tuple(results))


def _validate_metadata(
    payload: dict[str, Any],
    contract_type: str,
    errors: list[str],
    warnings: list[str],
    *,
    strict: bool,
) -> None:
    schema_version = payload.get("schema_version")
    if schema_version is None and contract_type == "snapshot" and not strict:
        warnings.append("Legacy snapshot missing schema_version; accepted for compatibility.")
    elif schema_version is None:
        errors.append("Missing core field: schema_version")
    elif str(schema_version) != SCHEMA_VERSION:
        message = (
            f"Unexpected schema_version {schema_version}; validator expects "
            f"{SCHEMA_VERSION}."
        )
        if strict:
            errors.append(message)
        else:
            warnings.append(message)
    if payload.get("generator") != GENERATOR and not (
        contract_type == "snapshot" and "schema_version" not in payload
    ):
        errors.append("Missing or invalid generator")
    if not payload.get("generated_at") and not (
        contract_type == "snapshot" and "schema_version" not in payload and not strict
    ):
        errors.append("Missing core field: generated_at")
    elif strict and payload.get("generated_at"):
        try:
            generated_at = datetime.fromisoformat(
                str(payload["generated_at"]).replace("Z", "+00:00")
            )
        except ValueError:
            errors.append("Invalid generated_at timestamp")
        else:
            if generated_at.tzinfo is None:
                errors.append("generated_at timestamp must include timezone")


def _validate_shape(payload: dict[str, Any], contract_type: str, errors: list[str]) -> None:
    list_fields = {
        "report": ("provider_health", "provider_warnings", "candidates", "risk_issues"),
        "trace": ("providers",),
        "research_context": ("artifacts", "warnings"),
        "evidence_bundle": ("findings", "evidence", "data_gaps", "warnings"),
        "research_answer": ("findings", "evidence", "data_gaps", "warnings"),
        "mcp_tool_result": ("warnings",),
        "release_readiness": (
            "observed_run_dates",
            "run_observations",
            "blockers",
            "warnings",
        ),
        "fund_profile": ("fees",),
    }
    dict_fields = {
        "report": ("valuations", "report_metadata"),
        "snapshot": ("candidates", "valuations"),
        "research_context": ("data", "metadata"),
        "evidence_bundle": ("metadata",),
        "research_answer": ("intent", "metadata"),
        "mcp_tool_result": ("data", "metadata"),
        "release_readiness": (
            "contract_summary",
            "performance",
            "boundaries",
            "required_provenance",
        ),
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


def _validate_fund_profile_values(payload: dict[str, Any], errors: list[str]) -> None:
    code = payload.get("code")
    if not isinstance(code, str) or len(code) != 6 or not code.isdigit():
        errors.append("Fund profile code must be a six-digit string")

    as_of = payload.get("as_of")
    if as_of is not None and not isinstance(as_of, str):
        errors.append("Field must be a string or null: as_of")

    statuses = {"updated", "attention", "limited", "unavailable"}
    for field in (
        "data_status",
        "profile_status",
        "trading_status",
        "fee_status",
    ):
        if payload.get(field) not in statuses:
            errors.append(f"Unsupported fund profile status: {field}={payload.get(field)}")

    expected_boundaries = {
        "not_production_model": True,
        "main_score_changed": False,
        "main_risk_changed": False,
    }
    for field, expected in expected_boundaries.items():
        if payload.get(field) is not expected:
            errors.append(
                f"Fund profile {field} must be {str(expected).lower()}"
            )

    for field in ("catalog", "profile", "trading_rule"):
        component = payload.get(field)
        if component is not None and not isinstance(component, dict):
            errors.append(f"Field must be an object or null: {field}")
            continue
        if isinstance(component, dict) and code and component.get("code") != code:
            errors.append(f"{field}.code must match the top-level code")

    fees = payload.get("fees")
    if not isinstance(fees, list):
        return
    for index, fee in enumerate(fees):
        if not isinstance(fee, dict):
            errors.append(f"fees[{index}] must be an object")
            continue
        if fee.get("code") != code:
            errors.append(f"fees[{index}].code must match the top-level code")
        if not isinstance(fee.get("fee_type"), str) or not fee.get("fee_type"):
            errors.append(f"fees[{index}].fee_type must be a non-empty string")
        for field in ("condition", "period", "channel", "original_rate", "discounted_rate"):
            value = fee.get(field)
            if value is not None and not isinstance(value, str):
                errors.append(f"fees[{index}].{field} must be a string or null")


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
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        expected_boundaries = {
            "read_only": True,
            "not_production_model": True,
            "main_score_changed": False,
            "main_risk_changed": False,
        }
        for field, expected in expected_boundaries.items():
            if metadata.get(field) is not expected:
                errors.append(
                    f"research_answer metadata.{field} must be "
                    f"{str(expected).lower()}"
                )

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


def _validate_release_readiness_values(payload: dict[str, Any], errors: list[str]) -> None:
    if payload.get("status") not in {"pass", "fail"}:
        errors.append(f"Unsupported release readiness status: {payload.get('status')}")
    for field in ("minimum_valid_runs", "valid_run_count"):
        value = payload.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"Field must be a non-negative integer: {field}")
    if not isinstance(payload.get("release_target"), str) or not payload.get("release_target"):
        errors.append("Field must be a non-empty string: release_target")
    mode = payload.get("observation_mode")
    if mode not in {"historical_compat", "post_rc"}:
        errors.append(f"Unsupported release observation mode: {mode}")
    provenance = payload.get("required_provenance")
    if mode == "post_rc" and isinstance(provenance, dict):
        if not provenance.get("app_version"):
            errors.append("Post-RC readiness requires app_version provenance")
        if not provenance.get("git_commit"):
            errors.append("Post-RC readiness requires git_commit provenance")
        if provenance.get("git_dirty") is not False:
            errors.append("Post-RC readiness requires git_dirty=false")
        if not isinstance(provenance.get("triggers"), list) or not provenance.get("triggers"):
            errors.append("Post-RC readiness requires scheduler triggers")
    if (
        payload.get("status") == "pass"
        and payload.get("release_target") == "v2.0.0"
        and mode != "post_rc"
    ):
        errors.append("Final v2.0.0 readiness requires post_rc observation mode")
    boundaries = payload.get("boundaries")
    if isinstance(boundaries, dict):
        expected = {
            "not_production_model": True,
            "main_score_changed": False,
            "main_risk_changed": False,
            "trading_enabled": False,
        }
        for field, value in expected.items():
            if boundaries.get(field) is not value:
                errors.append(f"Invalid release boundary: {field}")
    performance = payload.get("performance")
    if isinstance(performance, dict) and not isinstance(performance.get("within_budget"), bool):
        errors.append("Field must be a boolean: performance.within_budget")
    if payload.get("status") == "pass":
        minimum = payload.get("minimum_valid_runs")
        valid = payload.get("valid_run_count")
        if isinstance(minimum, int) and isinstance(valid, int) and valid < minimum:
            errors.append("Passing release readiness requires enough valid runs")
        if payload.get("blockers"):
            errors.append("Passing release readiness cannot contain blockers")
        contract_summary = payload.get("contract_summary")
        if isinstance(contract_summary, dict) and contract_summary.get("ok") is not True:
            errors.append("Passing release readiness requires valid contracts")
        if isinstance(performance, dict) and performance.get("within_budget") is not True:
            errors.append("Passing release readiness requires performance within budget")


def _latest_trace(output_dir: Path) -> Path | None:
    trace_dir = output_dir / "traces"
    if not trace_dir.exists():
        return None
    # Daily validation must never select an auxiliary provider trace such as
    # provider-sector-history-YYYY-MM-DD.json.
    candidates = sorted(trace_dir.glob("provider-????-??-??.json"))
    return candidates[-1] if candidates else None


def _latest_fund_profile(output_dir: Path) -> Path | None:
    profile_dir = output_dir / "fund_profiles"
    if not profile_dir.exists():
        return None
    candidates = list(profile_dir.glob("fund_profile-??????.json"))
    return max(candidates, key=lambda item: item.stat().st_mtime) if candidates else None
