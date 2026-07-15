from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .artifacts import ArtifactCatalog, ArtifactLoadResult, ArtifactLoader
from .models import ArtifactDescriptor, ResearchContext
from .redaction import sanitize_data


SUPPORTED_RESEARCH_TOPICS = ("market", "fund", "portfolio", "news", "history", "quality")

TOPIC_ARTIFACT_TYPES: dict[str, tuple[str, ...]] = {
    "market": ("market_intelligence", "market_trend", "market_theme_rankings"),
    "fund": ("fund_detail", "watchlist_fund_details"),
    "portfolio": ("portfolio_report",),
    "news": ("news_evidence",),
    "history": ("snapshot", "market_snapshot"),
    "quality": (
        "report",
        "provider_trace",
        "ops_status",
        "daily_research_summary",
        "long_horizon_stability",
    ),
}

MARKET_INTELLIGENCE_FIELDS = (
    "as_of",
    "source",
    "run_type",
    "total_funds",
    "total_etfs",
    "themes",
    "top_themes",
    "hot_theme_candidates",
    "insufficient_sample_themes",
    "data_quality_summary",
    "warnings",
)

MARKET_TREND_FIELDS = (
    "latest_as_of",
    "source",
    "period_days",
    "snapshots_processed",
    "minimum_required_snapshots",
    "enough_market_history",
    "persistent_hot_themes",
    "new_hot_themes",
    "disappeared_hot_themes",
    "rising_themes",
    "falling_themes",
    "insufficient_history_themes",
    "data_quality_trend",
    "warnings",
)


class ResearchQueryService:
    def __init__(self, output_dir: Path | str):
        self.output_dir = Path(output_dir)
        self.catalog = ArtifactCatalog(self.output_dir)
        self.loader = ArtifactLoader(self.output_dir)

    def query(self, topic: str, *, code: str | None = None) -> ResearchContext:
        normalized_topic = str(topic or "").strip().lower()
        if normalized_topic not in SUPPORTED_RESEARCH_TOPICS:
            raise ValueError(f"unsupported research topic: {topic}")
        normalized_code = str(code).strip() if code is not None else None
        descriptors = self._select_descriptors(normalized_topic)
        if not descriptors:
            return self._context(
                normalized_topic,
                status="unavailable",
                code=normalized_code,
                descriptors=(),
                data={},
                warnings=(f"no_artifacts_for_topic:{normalized_topic}",),
            )

        results = tuple(self.loader.load(descriptor) for descriptor in descriptors)
        load_failures = tuple(result for result in results if result.status != "ok")
        payloads = tuple(result for result in results if result.payload is not None)
        warnings = _collect_warnings(results)
        data, selection_warnings = self._build_data(normalized_topic, payloads, code=normalized_code)
        warnings = _deduplicate((*warnings, *selection_warnings))
        if not data:
            status = "unavailable" if not payloads else "partial"
        elif load_failures or selection_warnings:
            status = "partial"
        else:
            status = "ok"
        return self._context(
            normalized_topic,
            status=status,
            code=normalized_code,
            descriptors=descriptors,
            data=sanitize_data(data),
            warnings=warnings,
        )

    def _select_descriptors(self, topic: str) -> tuple[ArtifactDescriptor, ...]:
        allowed = set(TOPIC_ARTIFACT_TYPES[topic])
        selected = tuple(item for item in self.catalog.scan() if item.artifact_type in allowed)
        if topic == "history":
            return selected
        if topic == "fund":
            details = tuple(item for item in selected if item.artifact_type == "fund_detail")
            watchlist = _latest_per_type(
                item for item in selected if item.artifact_type == "watchlist_fund_details"
            )
            return tuple(sorted((*details, *watchlist), key=lambda item: (item.artifact_type, item.path)))
        return _latest_per_type(selected)

    def _build_data(
        self,
        topic: str,
        results: tuple[ArtifactLoadResult, ...],
        *,
        code: str | None,
    ) -> tuple[dict[str, Any], tuple[str, ...]]:
        if topic == "market":
            return _market_data(results), ()
        if topic == "fund":
            return _fund_data(results, code)
        if topic == "portfolio":
            return _single_payload(results, "portfolio_report", "portfolio"), ()
        if topic == "news":
            return _single_payload(results, "news_evidence", "news"), ()
        if topic == "history":
            return _history_data(results), ()
        return _quality_data(results), ()

    def _context(
        self,
        topic: str,
        *,
        status: str,
        code: str | None,
        descriptors: tuple[ArtifactDescriptor, ...],
        data: dict[str, Any],
        warnings: tuple[str, ...],
    ) -> ResearchContext:
        as_of_values = sorted(item.as_of for item in descriptors if item.as_of)
        return ResearchContext(
            schema_version="1.0",
            generated_at=datetime.now(timezone.utc).isoformat(),
            generator="fund_agent",
            topic=topic,
            status=status,
            as_of=as_of_values[-1] if as_of_values else None,
            code=code,
            artifacts=tuple(asdict(item) for item in descriptors),
            data=data,
            warnings=warnings,
            metadata={"compact": True, "full_payloads_embedded": False},
        )


def _market_data(results: tuple[ArtifactLoadResult, ...]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for result in results:
        payload = result.payload or {}
        if result.descriptor.artifact_type == "market_intelligence":
            data["market_intelligence"] = _pick(payload, MARKET_INTELLIGENCE_FIELDS)
        elif result.descriptor.artifact_type == "market_trend":
            data["market_trend"] = _pick(payload, MARKET_TREND_FIELDS)
        elif result.descriptor.artifact_type == "market_theme_rankings":
            data["theme_rankings"] = payload
    return data


def _fund_data(
    results: tuple[ArtifactLoadResult, ...],
    code: str | None,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    watchlist: dict[str, Any] | None = None
    details: list[dict[str, Any]] = []
    for result in results:
        payload = result.payload or {}
        if result.descriptor.artifact_type == "watchlist_fund_details":
            watchlist = payload
            details.extend(item for item in payload.get("fund_details", []) if isinstance(item, dict))
        elif result.descriptor.artifact_type == "fund_detail":
            details.append(payload)
    if code is None:
        if watchlist is None and not details:
            return {}, ()
        return {
            "funds": _deduplicate_funds(details),
            "coverage_summary": (watchlist or {}).get("coverage_summary", {}),
        }, ()
    match = next((item for item in details if _fund_code(item) == code), None)
    if match is None:
        return {
            "coverage_summary": (watchlist or {}).get("coverage_summary", {}),
        }, (f"fund_not_found:{code}",)
    return {
        "fund": match,
        "coverage_summary": (watchlist or {}).get("coverage_summary", {}),
    }, ()


def _history_data(results: tuple[ArtifactLoadResult, ...]) -> dict[str, Any]:
    entries: list[tuple[str, dict[str, Any], ArtifactDescriptor]] = []
    for result in results:
        payload = result.payload or {}
        as_of = str(payload.get("as_of") or result.descriptor.as_of or "")
        entries.append((as_of, payload, result.descriptor))
    entries.sort(key=lambda item: (item[0], item[2].path))
    timeline = [
        {
            "artifact_id": descriptor.artifact_id,
            "artifact_type": descriptor.artifact_type,
            "path": descriptor.path,
            "as_of": as_of or None,
            "quality_grade": descriptor.quality_grade,
            "stale": descriptor.stale,
        }
        for as_of, _, descriptor in entries
    ]
    latest_payload = entries[-1][1] if entries else {}
    latest_delta = latest_payload.get("snapshot_delta") or latest_payload.get("delta") or {}
    return {"timeline": timeline, "latest_delta": latest_delta}


def _quality_data(results: tuple[ArtifactLoadResult, ...]) -> dict[str, Any]:
    field_map: dict[str, tuple[str, ...]] = {
        "report": ("as_of", "data_quality_grade", "provider_health", "provider_warnings"),
        "provider_trace": ("as_of", "providers"),
        "ops_status": (
            "generated_at",
            "overall_status",
            "ops_ready",
            "dashboard_ready",
            "latest_run",
            "main_model_ready",
            "main_model_blockers",
        ),
        "daily_research_summary": (
            "as_of",
            "status",
            "data_quality_grade",
            "provider_warnings",
            "missing_artifacts",
        ),
        "long_horizon_stability": (
            "runs_processed",
            "minimum_required_runs",
            "enough_history",
            "blockers",
            "main_model_ready",
        ),
    }
    data: dict[str, Any] = {}
    for result in results:
        artifact_type = result.descriptor.artifact_type
        payload = result.payload or {}
        data[artifact_type] = _pick(payload, field_map.get(artifact_type, ()))
    return data


def _single_payload(
    results: tuple[ArtifactLoadResult, ...],
    artifact_type: str,
    output_key: str,
) -> dict[str, Any]:
    for result in results:
        if result.descriptor.artifact_type == artifact_type and result.payload is not None:
            return {output_key: result.payload}
    return {}


def _latest_per_type(descriptors: Iterable[ArtifactDescriptor]) -> tuple[ArtifactDescriptor, ...]:
    latest: dict[str, ArtifactDescriptor] = {}
    for descriptor in descriptors:
        current = latest.get(descriptor.artifact_type)
        if current is None or (descriptor.as_of or "", descriptor.path) > (current.as_of or "", current.path):
            latest[descriptor.artifact_type] = descriptor
    return tuple(sorted(latest.values(), key=lambda item: (item.artifact_type, item.path)))


def _collect_warnings(results: tuple[ArtifactLoadResult, ...]) -> tuple[str, ...]:
    warnings: list[str] = []
    for result in results:
        for warning in (*result.descriptor.warnings, *result.warnings):
            warnings.append(f"{result.descriptor.artifact_id}:{warning}")
    return _deduplicate(warnings)


def _pick(payload: dict[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    return {field: payload[field] for field in fields if field in payload}


def _fund_code(payload: dict[str, Any]) -> str | None:
    direct = payload.get("code")
    if direct is not None:
        return str(direct)
    fund = payload.get("fund")
    if isinstance(fund, dict) and fund.get("code") is not None:
        return str(fund["code"])
    return None


def _deduplicate_funds(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_code: dict[str, dict[str, Any]] = {}
    without_code: list[dict[str, Any]] = []
    for item in items:
        code = _fund_code(item)
        if code is None:
            without_code.append(item)
        else:
            by_code[code] = item
    return [*by_code.values(), *without_code]


def _deduplicate(items: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))
