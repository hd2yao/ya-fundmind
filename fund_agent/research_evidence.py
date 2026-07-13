from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from .models import ArtifactDescriptor, EvidenceRef, ResearchFinding


QUALITY_ORDER = {"normal": 0, "unknown": 1, "warning": 2, "degraded": 3, "blocked": 4}


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
