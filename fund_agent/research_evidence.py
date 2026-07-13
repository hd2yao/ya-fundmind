from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable

from .models import ArtifactDescriptor, EvidenceRef, ResearchFinding


QUALITY_ORDER = {"normal": 0, "unknown": 1, "warning": 2, "degraded": 3, "blocked": 4}


@dataclass(frozen=True)
class QualityDecision:
    grade: str
    review_required: bool
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceConflict:
    claim_type: str
    sources: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    values: tuple[Any, ...]
    quality_grade: str = "degraded"
    review_required: bool = True


def escape_json_pointer_token(token: str) -> str:
    return str(token).replace("~", "~0").replace("/", "~1")


def resolve_json_pointer(payload: Any, pointer: str) -> Any:
    if pointer == "":
        return payload
    if not pointer.startswith("/"):
        raise ValueError(f"Invalid JSON Pointer: {pointer}")
    current = payload
    for encoded_token in pointer[1:].split("/"):
        token = _decode_pointer_token(encoded_token, pointer)
        if isinstance(current, dict):
            if token not in current:
                raise ValueError(f"JSON Pointer path not found: {pointer}")
            current = current[token]
        elif isinstance(current, list):
            if not token.isdigit():
                raise ValueError(f"JSON Pointer list index is invalid: {pointer}")
            index = int(token)
            if index >= len(current):
                raise ValueError(f"JSON Pointer list index is out of range: {pointer}")
            current = current[index]
        else:
            raise ValueError(f"JSON Pointer cannot descend into scalar: {pointer}")
    return current


def build_evidence_ref(
    descriptor: ArtifactDescriptor,
    payload: dict[str, Any],
    *,
    json_pointer: str,
    claim_type: str,
    metadata: dict[str, Any] | None = None,
) -> EvidenceRef:
    value = resolve_json_pointer(payload, json_pointer)
    identity = f"{descriptor.artifact_id}:{json_pointer}:{claim_type}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return EvidenceRef(
        evidence_id=f"evidence-{digest[:20]}",
        artifact_id=descriptor.artifact_id,
        artifact_type=descriptor.artifact_type,
        path=descriptor.path,
        json_pointer=json_pointer,
        claim_type=claim_type,
        as_of=descriptor.as_of,
        source=descriptor.source,
        quality_grade=descriptor.quality_grade or "unknown",
        stale=descriptor.stale,
        value=value,
        excerpt=_excerpt(value),
        metadata=dict(metadata or {}),
    )


def build_finding(
    *,
    topic: str,
    category: str,
    label: str,
    value: Any,
    evidence: Iterable[EvidenceRef],
    code: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ResearchFinding | None:
    evidence_items = tuple(evidence)
    if not evidence_items:
        return None
    evidence_ids = tuple(item.evidence_id for item in evidence_items)
    identity = f"{topic}:{category}:{code or ''}:{label}:{':'.join(evidence_ids)}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return ResearchFinding(
        finding_id=f"finding-{digest[:20]}",
        topic=topic,
        category=category,
        label=label,
        value=value,
        code=code,
        quality_grade=_worst_quality(item.quality_grade for item in evidence_items),
        evidence_ids=evidence_ids,
        metadata=dict(metadata or {}),
    )


def evaluate_artifact_quality(
    descriptor: ArtifactDescriptor,
    payload: dict[str, Any],
) -> QualityDecision:
    grades = ["normal"]
    reasons: list[str] = []
    descriptor_grade = descriptor.quality_grade or "unknown"
    if descriptor_grade in {"warning", "degraded", "blocked", "critical"}:
        normalized = "blocked" if descriptor_grade == "critical" else descriptor_grade
        grades.append(normalized)
        reasons.append(f"artifact_quality:{descriptor_grade}")
    if descriptor.stale:
        grades.append("degraded")
        reasons.append("stale_artifact")
    if "schema_version_missing" in descriptor.warnings:
        grades.append("warning")
        reasons.append("legacy_schema")

    providers = _provider_records(payload)
    if any(provider.get("fallback_used") is True for provider in providers):
        grades.append("warning")
        reasons.append("provider_fallback")

    for warning in _provider_warnings(payload, providers):
        code = str(warning.get("code") or "unknown")
        severity = str(warning.get("severity") or "warning").lower()
        if severity in {"critical", "error"}:
            grades.append("blocked")
            reasons.append(f"critical_provider_warning:{code}")
        else:
            grades.append("warning")
            reasons.append(f"provider_warning:{code}")

    if _has_insufficient_sample(payload.get("warnings")):
        grades.append("warning")
        reasons.append("insufficient_sample")

    grade = _worst_quality(grades)
    return QualityDecision(
        grade=grade,
        review_required=grade in {"degraded", "blocked"},
        reasons=_deduplicate(reasons),
    )


def aggregate_quality(decisions: Iterable[QualityDecision]) -> QualityDecision:
    items = tuple(decisions)
    if not items:
        return QualityDecision("unknown", True, ("quality_evidence_missing",))
    grade = _worst_quality(item.grade for item in items)
    return QualityDecision(
        grade=grade,
        review_required=any(item.review_required for item in items),
        reasons=_deduplicate(reason for item in items for reason in item.reasons),
    )


def detect_evidence_conflicts(evidence: Iterable[EvidenceRef]) -> tuple[EvidenceConflict, ...]:
    groups: dict[tuple[str, Any], list[EvidenceRef]] = {}
    for item in evidence:
        key = (item.claim_type, item.metadata.get("code"))
        groups.setdefault(key, []).append(item)

    conflicts: list[EvidenceConflict] = []
    for (claim_type, _), items in sorted(groups.items(), key=lambda entry: str(entry[0])):
        sources = tuple(sorted({str(item.source) for item in items if item.source}))
        values_by_key: dict[str, Any] = {}
        for item in items:
            values_by_key[_value_key(item.value)] = item.value
        if len(sources) < 2 or len(values_by_key) < 2:
            continue
        conflicts.append(
            EvidenceConflict(
                claim_type=claim_type,
                sources=sources,
                evidence_ids=tuple(item.evidence_id for item in items),
                values=tuple(values_by_key.values()),
            )
        )
    return tuple(conflicts)


def _decode_pointer_token(token: str, pointer: str) -> str:
    decoded: list[str] = []
    index = 0
    while index < len(token):
        if token[index] != "~":
            decoded.append(token[index])
            index += 1
            continue
        if index + 1 >= len(token) or token[index + 1] not in {"0", "1"}:
            raise ValueError(f"Invalid JSON Pointer escape: {pointer}")
        decoded.append("~" if token[index + 1] == "0" else "/")
        index += 2
    return "".join(decoded)


def _excerpt(value: Any, *, limit: int = 240) -> str:
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


def _worst_quality(grades: Iterable[str]) -> str:
    normalized = tuple(grade if grade in QUALITY_ORDER else "unknown" for grade in grades)
    if not normalized:
        return "unknown"
    return max(normalized, key=lambda grade: QUALITY_ORDER[grade])


def _provider_records(payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    records = payload.get("provider_health") or payload.get("providers") or []
    if not isinstance(records, list):
        return ()
    return tuple(item for item in records if isinstance(item, dict))


def _provider_warnings(
    payload: dict[str, Any],
    providers: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    warnings: list[dict[str, Any]] = []
    top_level = payload.get("provider_warnings")
    if isinstance(top_level, list):
        warnings.extend(item for item in top_level if isinstance(item, dict))
    for provider in providers:
        provider_items = provider.get("warnings")
        if isinstance(provider_items, list):
            warnings.extend(item for item in provider_items if isinstance(item, dict))
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for warning in warnings:
        key = (str(warning.get("code") or "unknown"), str(warning.get("severity") or "warning"))
        unique[key] = warning
    return tuple(unique.values())


def _has_insufficient_sample(items: Any) -> bool:
    if not isinstance(items, list):
        return False
    for item in items:
        if isinstance(item, str) and "insufficient_sample" in item:
            return True
        if isinstance(item, dict) and "insufficient_sample" in str(item.get("code") or ""):
            return True
    return False


def _value_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _deduplicate(items: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))
