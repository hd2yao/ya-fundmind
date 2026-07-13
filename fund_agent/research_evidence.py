from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .artifacts import ArtifactLoader
from .models import (
    ArtifactDescriptor,
    EvidenceBundle,
    EvidenceRef,
    ResearchContext,
    ResearchFinding,
)


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


@dataclass(frozen=True)
class _FindingSpec:
    artifact_type: str
    json_pointer: str
    claim_type: str
    category: str
    label: str


@dataclass(frozen=True)
class _LoadedArtifact:
    descriptor: ArtifactDescriptor
    payload: dict[str, Any]
    quality: QualityDecision


MARKET_SPECS = (
    _FindingSpec("market_intelligence", "/total_funds", "market.total_funds", "breadth", "基金总数"),
    _FindingSpec("market_intelligence", "/total_etfs", "market.total_etfs", "breadth", "ETF 总数"),
    _FindingSpec("market_intelligence", "/top_themes", "market.top_themes", "theme", "主题排名"),
    _FindingSpec("market_intelligence", "/hot_theme_candidates", "market.hot_themes", "theme", "热门主题"),
    _FindingSpec("market_trend", "/rising_themes", "market.rising_themes", "trend", "上升主题"),
    _FindingSpec("market_trend", "/falling_themes", "market.falling_themes", "trend", "下降主题"),
    _FindingSpec("market_trend", "/persistent_hot_themes", "market.persistent_hot_themes", "trend", "持续热门主题"),
    _FindingSpec("market_trend", "/new_hot_themes", "market.new_hot_themes", "trend", "新热门主题"),
    _FindingSpec("market_trend", "/enough_market_history", "market.enough_history", "quality", "市场历史是否充足"),
)

PORTFOLIO_SPECS = (
    _FindingSpec("portfolio_report", "/holding_count", "portfolio.holding_count", "position", "持仓数量"),
    _FindingSpec("portfolio_report", "/total_value", "portfolio.total_value", "position", "组合总市值"),
    _FindingSpec("portfolio_report", "/theme_exposure", "portfolio.theme_exposure", "exposure", "主题暴露"),
    _FindingSpec("portfolio_report", "/fund_type_exposure", "portfolio.fund_type_exposure", "exposure", "基金类型暴露"),
    _FindingSpec("portfolio_report", "/concentration", "portfolio.concentration", "concentration", "集中度"),
    _FindingSpec("portfolio_report", "/observation_issues", "portfolio.observation_issues", "observation", "组合观察项"),
)

NEWS_SPECS = (
    _FindingSpec("news_evidence", "/evidence_count", "news.evidence_count", "coverage", "证据数量"),
    _FindingSpec("news_evidence", "/low_confidence_count", "news.low_confidence_count", "quality", "低置信度证据数量"),
    _FindingSpec("news_evidence", "/by_source", "news.by_source", "source", "证据来源分布"),
    _FindingSpec("news_evidence", "/by_theme", "news.by_theme", "theme", "主题证据分布"),
    _FindingSpec("news_evidence", "/by_fund", "news.by_fund", "fund", "基金证据分布"),
    _FindingSpec("news_evidence", "/items", "news.items", "evidence", "新闻证据明细"),
)

QUALITY_SPECS = (
    _FindingSpec("report", "/data_quality_grade", "quality.report_grade", "quality", "报告数据质量"),
    _FindingSpec("report", "/provider_warnings", "quality.provider_warnings", "quality", "Provider warnings"),
    _FindingSpec("ops_status", "/ops_ready", "quality.ops_ready", "readiness", "Ops 是否就绪"),
    _FindingSpec("ops_status", "/dashboard_ready", "quality.dashboard_ready", "readiness", "Dashboard 是否就绪"),
    _FindingSpec("daily_research_summary", "/status", "quality.daily_status", "readiness", "Daily 状态"),
    _FindingSpec("daily_research_summary", "/data_quality_grade", "quality.daily_grade", "quality", "Daily 数据质量"),
    _FindingSpec("long_horizon_stability", "/runs_processed", "quality.runs_processed", "history", "有效运行数量"),
    _FindingSpec("long_horizon_stability", "/blockers", "quality.main_model_blockers", "history", "主模型阻塞项"),
)

FUND_FIELDS: tuple[tuple[str, str, str, str], ...] = (
    ("code", "fund.code", "identity", "基金代码"),
    ("name", "fund.name", "identity", "基金名称"),
    ("fund_type", "fund.fund_type", "identity", "基金类型"),
    ("category", "fund.category", "identity", "基金分类"),
    ("primary_theme", "fund.primary_theme", "theme", "主要主题"),
    ("returns", "fund.returns", "performance", "收益窗口"),
    ("data_coverage", "fund.data_coverage", "quality", "数据覆盖"),
    ("peer_comparison", "fund.peer_comparison", "peer", "同类对比"),
    ("missing_fields", "fund.missing_fields", "quality", "缺失字段"),
    ("warnings", "fund.warnings", "quality", "基金详情 warnings"),
)


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


def build_evidence_bundle(
    context: ResearchContext | dict[str, Any],
    output_dir: Path | str,
) -> EvidenceBundle:
    context_payload = asdict(context) if isinstance(context, ResearchContext) else dict(context)
    topic = str(context_payload.get("topic") or "")
    code = context_payload.get("code")
    loader = ArtifactLoader(output_dir)
    loaded: list[_LoadedArtifact] = []
    load_warnings: list[str] = []
    load_decisions: list[QualityDecision] = []
    for item in context_payload.get("artifacts") or []:
        try:
            descriptor = _descriptor_from_dict(item)
        except (KeyError, TypeError, ValueError) as exc:
            load_warnings.append(f"invalid_artifact_descriptor:{exc}")
            load_decisions.append(QualityDecision("blocked", True, ("invalid_artifact_descriptor",)))
            continue
        result = loader.load(descriptor)
        if result.status != "ok" or result.payload is None:
            reason = f"artifact_load_{result.status}:{descriptor.artifact_id}"
            grade = "blocked" if result.status == "blocked" else "warning"
            load_warnings.extend(result.warnings)
            load_decisions.append(QualityDecision(grade, grade == "blocked", (reason,)))
            continue
        decision = evaluate_artifact_quality(descriptor, result.payload)
        loaded.append(_LoadedArtifact(descriptor, result.payload, decision))
        load_decisions.append(decision)

    evidence: list[EvidenceRef] = []
    findings: list[ResearchFinding] = []
    data_gaps: list[str] = []
    if topic == "fund":
        _build_fund_evidence(loaded, str(code) if code is not None else None, evidence, findings, data_gaps)
    elif topic == "history":
        _build_history_evidence(loaded, evidence, findings, data_gaps)
    else:
        specs = {
            "market": MARKET_SPECS,
            "portfolio": PORTFOLIO_SPECS,
            "news": NEWS_SPECS,
            "quality": QUALITY_SPECS,
        }.get(topic, ())
        _build_spec_evidence(loaded, topic, specs, evidence, findings, data_gaps, code=None)

    evidence = list({item.evidence_id: item for item in evidence}.values())
    conflicts = detect_evidence_conflicts(evidence)
    conflict_evidence_ids = {evidence_id for conflict in conflicts for evidence_id in conflict.evidence_ids}
    if conflict_evidence_ids:
        findings = [
            replace(
                finding,
                quality_grade="degraded",
                review_required=True,
                warnings=_deduplicate((*finding.warnings, "evidence_conflict")),
            )
            if set(finding.evidence_ids) & conflict_evidence_ids
            else finding
            for finding in findings
        ]

    decisions = list(load_decisions)
    if data_gaps:
        decisions.append(QualityDecision("warning", False, ("data_gaps_present",)))
    if conflicts:
        decisions.append(QualityDecision("degraded", True, ("evidence_conflict",)))
    if not findings:
        decisions.append(QualityDecision("blocked", True, ("finding_evidence_missing",)))
    aggregate = aggregate_quality(decisions)
    context_status = str(context_payload.get("status") or "unavailable")
    if not findings:
        status = "unavailable"
    elif context_status != "ok" or data_gaps or load_warnings or conflicts:
        status = "partial"
    else:
        status = "ok"
    warnings = _deduplicate(
        (
            *(str(item) for item in context_payload.get("warnings") or []),
            *load_warnings,
            *aggregate.reasons,
            *(f"evidence_conflict:{conflict.claim_type}" for conflict in conflicts),
        )
    )
    return EvidenceBundle(
        schema_version="1.0",
        generated_at=datetime.now(timezone.utc).isoformat(),
        generator="fund_agent",
        topic=topic,
        status=status,
        as_of=context_payload.get("as_of"),
        code=str(code) if code is not None else None,
        quality_grade=aggregate.grade,
        review_required=aggregate.review_required,
        findings=tuple(asdict(item) for item in findings),
        evidence=tuple(asdict(item) for item in evidence),
        data_gaps=_deduplicate(data_gaps),
        warnings=warnings,
        metadata={
            "source_context_schema_version": context_payload.get("schema_version"),
            "artifact_count": len(context_payload.get("artifacts") or []),
            "finding_count": len(findings),
            "evidence_count": len(evidence),
            "conflict_count": len(conflicts),
            "not_production_model": True,
            "main_score_changed": False,
            "main_risk_changed": False,
        },
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


def _build_spec_evidence(
    loaded: Iterable[_LoadedArtifact],
    topic: str,
    specs: Iterable[_FindingSpec],
    evidence: list[EvidenceRef],
    findings: list[ResearchFinding],
    data_gaps: list[str],
    *,
    code: str | None,
) -> None:
    items = tuple(loaded)
    for spec in specs:
        matches = tuple(item for item in items if item.descriptor.artifact_type == spec.artifact_type)
        found = False
        for item in matches:
            if _add_pointer_finding(
                item,
                topic=topic,
                spec=spec,
                evidence=evidence,
                findings=findings,
                code=code,
            ):
                found = True
        if not found:
            data_gaps.append(spec.claim_type)


def _build_fund_evidence(
    loaded: Iterable[_LoadedArtifact],
    code: str | None,
    evidence: list[EvidenceRef],
    findings: list[ResearchFinding],
    data_gaps: list[str],
) -> None:
    items = tuple(loaded)
    for field_name, claim_type, category, label in FUND_FIELDS:
        found = False
        for item in items:
            prefix = ""
            if item.descriptor.artifact_type == "fund_detail":
                item_code = _payload_fund_code(item.payload)
                if code is not None and item_code != code:
                    continue
            elif item.descriptor.artifact_type == "watchlist_fund_details":
                index = _watchlist_fund_index(item.payload, code)
                if index is None:
                    continue
                prefix = f"/fund_details/{index}"
            else:
                continue
            spec = _FindingSpec(
                item.descriptor.artifact_type,
                f"{prefix}/{escape_json_pointer_token(field_name)}",
                claim_type,
                category,
                label,
            )
            if _add_pointer_finding(
                item,
                topic="fund",
                spec=spec,
                evidence=evidence,
                findings=findings,
                code=code,
            ):
                found = True
        if not found:
            data_gaps.append(claim_type)


def _build_history_evidence(
    loaded: Iterable[_LoadedArtifact],
    evidence: list[EvidenceRef],
    findings: list[ResearchFinding],
    data_gaps: list[str],
) -> None:
    items = tuple(loaded)
    if not items:
        data_gaps.extend(("history.latest_as_of", "history.latest_delta"))
        return
    latest = max(
        items,
        key=lambda item: (
            item.descriptor.as_of or str(item.payload.get("as_of") or ""),
            item.descriptor.artifact_type == "snapshot",
            item.descriptor.path,
        ),
    )
    specs = (
        _FindingSpec(latest.descriptor.artifact_type, "/as_of", "history.latest_as_of", "history", "最新历史日期"),
        _FindingSpec(latest.descriptor.artifact_type, "/snapshot_delta", "history.latest_delta", "change", "最新历史变化"),
    )
    for spec in specs:
        if not _add_pointer_finding(
            latest,
            topic="history",
            spec=spec,
            evidence=evidence,
            findings=findings,
            code=None,
        ):
            data_gaps.append(spec.claim_type)


def _add_pointer_finding(
    item: _LoadedArtifact,
    *,
    topic: str,
    spec: _FindingSpec,
    evidence: list[EvidenceRef],
    findings: list[ResearchFinding],
    code: str | None,
) -> bool:
    try:
        evidence_item = build_evidence_ref(
            item.descriptor,
            item.payload,
            json_pointer=spec.json_pointer,
            claim_type=spec.claim_type,
            metadata={"code": code} if code is not None else {},
        )
    except ValueError:
        return False
    evidence_item = replace(evidence_item, quality_grade=item.quality.grade)
    finding = build_finding(
        topic=topic,
        category=spec.category,
        label=spec.label,
        value=evidence_item.value,
        evidence=(evidence_item,),
        code=code,
        metadata={"claim_type": spec.claim_type},
    )
    if finding is None:
        return False
    finding = replace(
        finding,
        quality_grade=item.quality.grade,
        review_required=item.quality.review_required,
        warnings=item.quality.reasons,
    )
    evidence.append(evidence_item)
    findings.append(finding)
    return True


def _descriptor_from_dict(payload: dict[str, Any]) -> ArtifactDescriptor:
    names = {item.name for item in fields(ArtifactDescriptor)}
    values = {key: value for key, value in payload.items() if key in names}
    if "warnings" in values:
        values["warnings"] = tuple(values["warnings"] or ())
    values.setdefault("metadata", {})
    return ArtifactDescriptor(**values)


def _payload_fund_code(payload: dict[str, Any]) -> str | None:
    if payload.get("code") is not None:
        return str(payload["code"])
    fund = payload.get("fund")
    if isinstance(fund, dict) and fund.get("code") is not None:
        return str(fund["code"])
    return None


def _watchlist_fund_index(payload: dict[str, Any], code: str | None) -> int | None:
    details = payload.get("fund_details")
    if not isinstance(details, list):
        return None
    if code is None:
        return 0 if details else None
    for index, item in enumerate(details):
        if isinstance(item, dict) and str(item.get("code") or "") == code:
            return index
    return None


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
