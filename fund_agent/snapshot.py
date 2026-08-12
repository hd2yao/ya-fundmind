from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agents import ResearchResult

SCHEMA_VERSION = "1.0"
GENERATOR = "fund_agent"


def snapshot_from_result(result: ResearchResult) -> dict[str, Any]:
    portfolio = None
    if result.portfolio:
        portfolio = {
            "total_value": result.portfolio.total_value,
            "total_unrealized_return_pct": result.portfolio.total_unrealized_return_pct,
            "risk_issues": [
                {
                    "code": issue.code,
                    "severity": issue.severity,
                    "message": issue.message,
                }
                for issue in result.portfolio.risk_issues
            ],
            "positions": [
                {
                    "code": position.holding.code,
                    "name": position.holding.name,
                    "current_value": position.current_value,
                    "weight": position.weight,
                    "target_drift": position.target_drift,
                    "unrealized_return_pct": position.unrealized_return_pct,
                }
                for position in result.portfolio.positions
            ],
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _generated_at(),
        "generator": GENERATOR,
        "as_of": result.as_of,
        "candidates": {
            candidate.fund.code: {
                "code": candidate.fund.code,
                "name": candidate.fund.name,
                "score": candidate.total_score,
                "evidence_label": candidate.evidence_label,
            }
            for candidate in result.ranked_candidates
        },
        "valuations": {
            code: {
                "code": code,
                "method": valuation.method,
                "estimated_value": valuation.estimated_value,
                "confidence": valuation.confidence,
            }
            for code, valuation in result.valuations.items()
        },
        "portfolio": portfolio,
        "provider_health": [provider_health_to_dict(item) for item in result.provider_health],
        "data_quality_grade": result.data_quality_grade,
    }


def provider_health_to_dict(item) -> dict[str, Any]:
    return {
        "provider": item.provider,
        "provider_version": item.provider_version,
        "started_at": item.started_at,
        "finished_at": item.finished_at,
        "duration_ms": item.duration_ms,
        "live_row_count": item.live_row_count,
        "mapped_row_count": item.mapped_row_count,
        "skipped_row_count": item.skipped_row_count,
        "cache_read_count": item.cache_read_count,
        "cache_write_count": item.cache_write_count,
        "fallback_used": item.fallback_used,
        "fallback_reason": item.fallback_reason,
        "fallback_source": item.fallback_source,
        "watchlist_requested_count": item.watchlist_requested_count,
        "watchlist_matched_count": item.watchlist_matched_count,
        "watchlist_missing_codes": list(item.watchlist_missing_codes),
        "warnings": [
            {
                "code": warning.code,
                "message": warning.message,
                "severity": warning.severity,
                "details": warning.details,
            }
            for warning in item.warnings
        ],
        "endpoints": [
            {
                "endpoint": endpoint.endpoint,
                "started_at": endpoint.started_at,
                "finished_at": endpoint.finished_at,
                "duration_ms": endpoint.duration_ms,
                "attempts": endpoint.attempts,
                "success": endpoint.success,
                "error": endpoint.error,
                "timeout_seconds": endpoint.timeout_seconds,
                "live_row_count": endpoint.live_row_count,
                "mapped_row_count": endpoint.mapped_row_count,
                "skipped_row_count": endpoint.skipped_row_count,
                "cache_read_count": endpoint.cache_read_count,
                "cache_write_count": endpoint.cache_write_count,
            }
            for endpoint in item.endpoints
        ],
        **_provider_metadata_fields(item.metadata),
    }


def _provider_metadata_fields(metadata: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "windows_requested",
        "windows_generated",
        "operation",
        "sector_symbol",
        "sector_name",
    }
    return {key: value for key, value in metadata.items() if key in allowed}


# Compatibility for existing private imports while callers move to the public helper.
_provider_health_to_dict = provider_health_to_dict


def write_snapshot(result: ResearchResult, output_dir: Path | str) -> Path:
    output_path = Path(output_dir)
    snapshot_dir = output_path / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_dir / f"{result.as_of}.json"
    path.write_text(
        json.dumps(snapshot_from_result(result), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def load_previous_snapshot(output_dir: Path | str, as_of: str) -> dict[str, Any] | None:
    snapshot_dir = Path(output_dir) / "snapshots"
    if not snapshot_dir.exists():
        return None
    candidates = sorted(
        path for path in snapshot_dir.glob("*.json") if path.stem < as_of
    )
    if not candidates:
        return None
    return json.loads(candidates[-1].read_text(encoding="utf-8"))


def compare_snapshots(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
) -> dict[str, Any] | None:
    if previous is None:
        return None
    return {
        "previous_as_of": previous.get("as_of"),
        "current_as_of": current.get("as_of"),
        "score_changes": _score_changes(previous, current),
        "valuation_changes": _valuation_changes(previous, current),
        "risk_changes": _risk_changes(previous, current),
        "holding_risk_changes": _holding_risk_changes(previous, current),
        "data_quality_grade_delta": _data_quality_grade_delta(previous, current),
        "provider_health_delta": _provider_health_delta(previous, current),
    }


def _score_changes(previous: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    previous_candidates = previous.get("candidates", {})
    for code, item in current.get("candidates", {}).items():
        previous_item = previous_candidates.get(code)
        if not previous_item:
            continue
        delta = round(float(item["score"]) - float(previous_item["score"]), 2)
        if delta:
            changes.append(
                {
                    "code": code,
                    "name": item.get("name", code),
                    "previous": previous_item["score"],
                    "current": item["score"],
                    "delta": delta,
                }
            )
    return changes


def _valuation_changes(previous: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    previous_valuations = previous.get("valuations", {})
    for code, item in current.get("valuations", {}).items():
        previous_item = previous_valuations.get(code)
        if not previous_item:
            continue
        value_delta = _number_delta(
            previous_item.get("estimated_value"),
            item.get("estimated_value"),
        )
        changed = (
            value_delta not in (None, 0)
            or previous_item.get("method") != item.get("method")
            or previous_item.get("confidence") != item.get("confidence")
        )
        if changed:
            changes.append(
                {
                    "code": code,
                    "previous_value": previous_item.get("estimated_value"),
                    "current_value": item.get("estimated_value"),
                    "value_delta": value_delta,
                    "previous_method": previous_item.get("method"),
                    "current_method": item.get("method"),
                    "previous_confidence": previous_item.get("confidence"),
                    "current_confidence": item.get("confidence"),
                }
            )
    return changes


def _risk_changes(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    previous_risks = _risk_map(previous)
    current_risks = _risk_map(current)
    return {
        "added": [current_risks[key] for key in sorted(current_risks.keys() - previous_risks.keys())],
        "resolved": [
            previous_risks[key] for key in sorted(previous_risks.keys() - current_risks.keys())
        ],
    }


def _holding_risk_changes(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    previous_portfolio = previous.get("portfolio") or {}
    current_portfolio = current.get("portfolio") or {}
    previous_risk_count = len(previous_portfolio.get("risk_issues", []))
    current_risk_count = len(current_portfolio.get("risk_issues", []))
    return {
        "total_value_delta": _number_delta(
            previous_portfolio.get("total_value"),
            current_portfolio.get("total_value"),
        ),
        "total_return_delta": _number_delta(
            previous_portfolio.get("total_unrealized_return_pct"),
            current_portfolio.get("total_unrealized_return_pct"),
        ),
        "risk_count_delta": current_risk_count - previous_risk_count,
    }


def _risk_map(snapshot: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    portfolio = snapshot.get("portfolio") or {}
    return {
        (str(item.get("code", "")), str(item.get("message", ""))): item
        for item in portfolio.get("risk_issues", [])
    }


def _number_delta(previous: object, current: object) -> float | None:
    if previous is None or current is None:
        return None
    return round(float(current) - float(previous), 4)


def _data_quality_grade_delta(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, str] | None:
    previous_grade = previous.get("data_quality_grade")
    current_grade = current.get("data_quality_grade")
    if previous_grade == current_grade:
        return None
    return {"previous": str(previous_grade or "unknown"), "current": str(current_grade or "unknown")}


def _provider_health_delta(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, dict[str, Any]]:
    previous_map = _provider_health_map(previous)
    current_map = _provider_health_map(current)
    delta: dict[str, dict[str, Any]] = {}
    for provider, item in current_map.items():
        previous_item = previous_map.get(provider, {})
        delta[provider] = {
            "provider_live_rows_delta": int(item.get("live_row_count", 0) or 0)
            - int(previous_item.get("live_row_count", 0) or 0),
            "provider_skipped_rows_delta": int(item.get("skipped_row_count", 0) or 0)
            - int(previous_item.get("skipped_row_count", 0) or 0),
            "provider_cache_writes_delta": int(item.get("cache_write_count", 0) or 0)
            - int(previous_item.get("cache_write_count", 0) or 0),
            "warning_count_delta": len(item.get("warnings", []) or [])
            - len(previous_item.get("warnings", []) or []),
            "fallback_changed": bool(item.get("fallback_used", False))
            != bool(previous_item.get("fallback_used", False)),
        }
    return delta


def _provider_health_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("provider", "")): item
        for item in snapshot.get("provider_health", []) or []
        if item.get("provider")
    }


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()
