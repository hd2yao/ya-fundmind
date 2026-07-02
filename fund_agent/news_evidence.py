from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .providers import normalize_fund_code


SCHEMA_VERSION = "1.0"
GENERATOR = "fund_agent.news_evidence"
EVIDENCE_STRENGTHS = {"low", "medium", "high"}


@dataclass(frozen=True)
class NewsEvidenceItem:
    evidence_id: str
    title: str
    source: str
    published_at: str | None
    url: str | None = None
    related_themes: tuple[str, ...] = ()
    related_funds: tuple[str, ...] = ()
    evidence_strength: str = "low"
    source_quality: str = "low_confidence"
    low_confidence: bool = True
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


def collect_news_evidence(
    *,
    source: str = "fixture",
    fixtures_file: Path | str = Path("data/fixtures/news_evidence.json"),
    output_dir: Path | str = Path("outputs"),
    as_of: str | None = None,
) -> dict[str, Any]:
    if source != "fixture":
        raise ValueError(f"Unsupported news evidence source: {source}")
    rows = _load_fixture_rows(Path(fixtures_file))
    items, duplicate_count, mapping_warnings = _normalize_rows(rows)
    payload = _build_report(
        items,
        source=source,
        duplicate_count=duplicate_count,
        mapping_warnings=mapping_warnings,
        as_of=as_of or date.today().isoformat(),
    )
    write_news_evidence_outputs(payload, output_dir)
    return payload


def write_news_evidence_outputs(payload: dict[str, Any], output_dir: Path | str) -> tuple[Path, Path, Path | None]:
    root = Path(output_dir)
    news_dir = root / "news"
    news_dir.mkdir(parents=True, exist_ok=True)
    report_path = news_dir / "news_evidence_report.json"
    summary_path = news_dir / "news_evidence_summary.md"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    summary_path.write_text(render_news_evidence_summary(payload), encoding="utf-8")
    run_path = None
    as_of = str(payload.get("as_of") or "")
    if as_of:
        run_dir = root / "runs" / as_of
        run_dir.mkdir(parents=True, exist_ok=True)
        run_path = run_dir / "news_evidence_report.json"
        run_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return report_path, summary_path, run_path


def render_news_evidence_summary(payload: dict[str, Any]) -> str:
    lines = [
        "# News Evidence",
        "",
        f"- as_of: {payload.get('as_of')}",
        f"- source: {payload.get('source')}",
        f"- evidence_count: {payload.get('evidence_count', 0)}",
        f"- duplicate_count: {payload.get('duplicate_count', 0)}",
        f"- low_confidence_count: {payload.get('low_confidence_count', 0)}",
        f"- not_production_model: {payload.get('not_production_model')}",
        f"- main_score_changed: {payload.get('main_score_changed')}",
        f"- main_risk_changed: {payload.get('main_risk_changed')}",
        "",
        "本报告仅整理新闻/公告证据候选，不修改主评分/主风险，不构成投资建议。",
        "",
        "## Evidence Items",
        "",
    ]
    for item in payload.get("items") or []:
        themes = ", ".join(item.get("related_themes") or []) or "none"
        funds = ", ".join(item.get("related_funds") or []) or "none"
        warnings = ", ".join(item.get("warnings") or []) or "none"
        lines.extend(
            [
                f"- {item.get('title')}",
                f"  - source: {item.get('source')}",
                f"  - published_at: {item.get('published_at')}",
                f"  - related_themes: {themes}",
                f"  - related_funds: {funds}",
                f"  - evidence_strength: {item.get('evidence_strength')}",
                f"  - source_quality: {item.get('source_quality')}",
                f"  - warnings: {warnings}",
            ]
        )
    return "\n".join(lines) + "\n"


def _load_fixture_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("news evidence fixture must be a list or contain an items list")
    return [item for item in rows if isinstance(item, dict)]


def _normalize_rows(rows: list[dict[str, Any]]) -> tuple[list[NewsEvidenceItem], int, list[str]]:
    items: list[NewsEvidenceItem] = []
    seen: set[tuple[str, str, str, str]] = set()
    duplicate_count = 0
    mapping_warnings: list[str] = []
    for index, row in enumerate(rows):
        try:
            item = _normalize_item(row)
        except ValueError as exc:
            mapping_warnings.append(f"row_{index}: {exc}")
            continue
        dedupe_key = (
            item.title,
            item.source,
            item.published_at or "",
            item.url or "",
        )
        if dedupe_key in seen:
            duplicate_count += 1
            continue
        seen.add(dedupe_key)
        items.append(item)
    return items, duplicate_count, mapping_warnings


def _normalize_item(row: dict[str, Any]) -> NewsEvidenceItem:
    title = str(row.get("title") or "").strip()
    if not title:
        raise ValueError("missing title")
    source = str(row.get("source") or "unknown").strip() or "unknown"
    published_at = _normalize_timestamp(row.get("published_at"))
    url = str(row.get("url") or "").strip() or None
    related_themes = tuple(str(item).strip() for item in _as_list(row.get("related_themes")) if str(item).strip())
    related_funds = tuple(
        code
        for code in (normalize_fund_code(item) for item in _as_list(row.get("related_funds")))
        if code
    )
    strength = str(row.get("evidence_strength") or "low").strip().lower()
    if strength not in EVIDENCE_STRENGTHS:
        strength = "low"
    warnings = []
    if not url:
        warnings.append("missing_url")
    if published_at is None:
        warnings.append("missing_published_at")
    if source == "unknown" or source.startswith("unknown"):
        warnings.append("unknown_source")
    low_confidence = bool(warnings or strength == "low")
    if low_confidence:
        warnings.insert(0, "low_confidence")
    source_quality = "low_confidence" if low_confidence else "verified"
    evidence_id = _evidence_id(title, source, published_at, url)
    return NewsEvidenceItem(
        evidence_id=evidence_id,
        title=title,
        source=source,
        published_at=published_at,
        url=url,
        related_themes=related_themes,
        related_funds=related_funds,
        evidence_strength=strength,
        source_quality=source_quality,
        low_confidence=low_confidence,
        warnings=tuple(dict.fromkeys(warnings)),
        metadata=dict(row.get("metadata") or {}),
    )


def _build_report(
    items: list[NewsEvidenceItem],
    *,
    source: str,
    duplicate_count: int,
    mapping_warnings: list[str],
    as_of: str,
) -> dict[str, Any]:
    by_theme = _count_by(items, "related_themes")
    by_fund = _count_by(items, "related_funds")
    by_source: dict[str, int] = {}
    for item in items:
        by_source[item.source] = by_source.get(item.source, 0) + 1
    low_confidence_count = sum(1 for item in items if item.low_confidence)
    warnings = list(mapping_warnings)
    if low_confidence_count:
        warnings.append("low_confidence_evidence_present")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": GENERATOR,
        "as_of": as_of,
        "source": source,
        "evidence_count": len(items),
        "duplicate_count": duplicate_count,
        "low_confidence_count": low_confidence_count,
        "by_theme": by_theme,
        "by_fund": by_fund,
        "by_source": by_source,
        "items": [asdict(item) for item in items],
        "warnings": warnings,
        "not_production_model": True,
        "main_score_changed": False,
        "main_risk_changed": False,
    }


def _count_by(items: list[NewsEvidenceItem], attr: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        values = getattr(item, attr)
        for value in values:
            counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _normalize_timestamp(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if len(text) == 10:
            return datetime.fromisoformat(text).replace(tzinfo=timezone.utc).isoformat()
        normalized = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except ValueError:
        return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _evidence_id(title: str, source: str, published_at: str | None, url: str | None) -> str:
    raw = "|".join([title, source, published_at or "", url or ""])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
