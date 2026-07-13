from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .models import ArtifactDescriptor


ARTIFACT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("report", "fund_agent_report.json"),
    ("snapshot", "snapshots/*.json"),
    ("provider_trace", "traces/*.json"),
    ("market_intelligence", "market/market_intelligence_report.json"),
    ("market_trend", "market/market_trend_report.json"),
    ("market_theme_rankings", "market/market_theme_rankings.json"),
    ("market_fund_candidates", "market/market_fund_candidates.json"),
    ("market_snapshot", "market/snapshots/*.json"),
    ("watchlist_fund_details", "fund_details/watchlist_fund_details.json"),
    ("fund_detail", "fund_details/fund_detail_*.json"),
    ("portfolio_report", "portfolio/portfolio_report.json"),
    ("news_evidence", "news/news_evidence_report.json"),
    ("ops_status", "ops_status.json"),
    ("daily_research_summary", "daily_research_summary.json"),
    ("weekly_research_summary", "weekly_research_summary.json"),
    ("long_horizon_stability", "long_horizon_stability.json"),
    ("latest_summary", "latest_summary.json"),
    ("run_daily_summary", "runs/*/daily_research_summary.json"),
    ("run_metadata", "runs/*/run_metadata.json"),
)


class ArtifactCatalog:
    def __init__(self, output_dir: Path | str):
        self.output_dir = Path(output_dir)

    def scan(self) -> tuple[ArtifactDescriptor, ...]:
        descriptors: list[ArtifactDescriptor] = []
        seen: set[Path] = set()
        for artifact_type, pattern in ARTIFACT_PATTERNS:
            for path in self.output_dir.glob(pattern):
                if not path.is_file() or path in seen:
                    continue
                seen.add(path)
                descriptors.append(self._describe(path, artifact_type))
        return tuple(sorted(descriptors, key=lambda item: (item.artifact_type, item.path)))

    def find(self, *, artifact_type: str) -> tuple[ArtifactDescriptor, ...]:
        return tuple(item for item in self.scan() if item.artifact_type == artifact_type)

    def _describe(self, path: Path, artifact_type: str) -> ArtifactDescriptor:
        relative_path = path.relative_to(self.output_dir).as_posix()
        payload, warnings = _read_metadata(path)
        source = _string_value(payload.get("source"))
        if source is None:
            source = _provider_source(payload)
        return ArtifactDescriptor(
            artifact_id=_artifact_id(artifact_type, relative_path),
            artifact_type=artifact_type,
            path=relative_path,
            schema_version=_string_value(payload.get("schema_version")),
            as_of=_string_value(payload.get("as_of") or payload.get("latest_as_of")),
            generated_at=_string_value(payload.get("generated_at")),
            source=source,
            quality_grade=_string_value(payload.get("data_quality_grade")),
            stale=bool(payload.get("stale", False)),
            content_hash=_content_hash(path),
            warnings=warnings,
        )


def _read_metadata(path: Path) -> tuple[dict[str, Any], tuple[str, ...]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}, ("invalid_json",)
    if not isinstance(payload, dict):
        return {}, ("invalid_json_root",)
    return payload, ()


def _artifact_id(artifact_type: str, relative_path: str) -> str:
    digest = hashlib.sha256(f"{artifact_type}:{relative_path}".encode("utf-8")).hexdigest()
    return f"artifact-{digest[:20]}"


def _content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _string_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _provider_source(payload: dict[str, Any]) -> str | None:
    health = payload.get("provider_health")
    if not isinstance(health, list) or not health or not isinstance(health[0], dict):
        return None
    return _string_value(health[0].get("provider"))
