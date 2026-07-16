from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from . import __version__
from .web_console import build_web_console_state


REPORT_ALLOWLIST = {
    "latest_summary": ("最新摘要", "latest_summary.md"),
    "fund_agent_report": ("基金研究主报告", "fund_agent_report.html"),
    "dashboard": ("研究总览", "dashboard/index.html"),
    "market": ("市场情报", "dashboard/market.html"),
    "funds": ("自选研究", "dashboard/funds.html"),
    "portfolio": ("组合分析", "dashboard/portfolio.html"),
    "news": ("新闻证据", "dashboard/news.html"),
    "review": ("人工审核", "dashboard/review.html"),
}


def create_web_app(
    *,
    output_dir: Path | str = Path("outputs"),
    review_state_path: Path | str | None = None,
) -> FastAPI:
    """Build the local product Web Console API with fixed filesystem roots."""

    root = Path(output_dir).expanduser().resolve()
    state_path = (
        Path(review_state_path).expanduser().resolve()
        if review_state_path is not None
        else root / "manual_review_state.json"
    )
    app = FastAPI(
        title="YA FundMind OS Local API",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.output_dir = root
    app.state.review_state_path = state_path

    @app.get("/api/health")
    def health() -> dict[str, object]:
        return {
            "status": "ready",
            "generator": f"ya-fundmind/{__version__}",
            "local_only": True,
            "output_status": "available" if root.is_dir() else "missing_outputs",
            "not_production_model": True,
            "main_score_changed": False,
            "main_risk_changed": False,
        }

    @app.get("/api/overview")
    def overview() -> dict[str, object]:
        state = build_web_console_state(output_dir=root, review_state_path=state_path)
        data = {
            "ops_status": _sanitize_local_paths(state.get("ops_status") or {}),
            "latest_summary_data": state.get("latest_summary_data") or {},
            "review_queue_count": state.get("review_queue_count", 0),
            "review_state_summary": state.get("review_state_summary") or {},
            "not_production_model": True,
            "main_score_changed": False,
            "main_risk_changed": False,
        }
        source_paths = (
            root / "daily_research_summary.json",
            root / "latest_summary.json",
            root / "latest_summary.md",
        )
        return _resource(
            data,
            source_paths=source_paths,
            available=any(path.is_file() for path in source_paths),
        )

    @app.get("/api/market")
    def market() -> dict[str, object]:
        intelligence_path = root / "market" / "market_intelligence_report.json"
        trend_path = root / "market" / "market_trend_report.json"
        return _resource(
            {
                "intelligence": _load_json(intelligence_path),
                "trend": _load_json(trend_path),
            },
            source_paths=(intelligence_path, trend_path),
        )

    @app.get("/api/funds")
    def funds() -> dict[str, object]:
        details_path = root / "fund_details" / "watchlist_fund_details.json"
        signals_path = root / "signal_candidates.json"
        return _resource(
            {
                "details": _load_json(details_path),
                "signal_candidates": _load_json(signals_path),
            },
            source_paths=(details_path, signals_path),
        )

    @app.get("/api/portfolio")
    def portfolio() -> dict[str, object]:
        path = root / "portfolio" / "portfolio_report.json"
        return _resource(_load_json(path), source_paths=(path,))

    @app.get("/api/news")
    def news() -> dict[str, object]:
        path = root / "news" / "news_evidence_report.json"
        return _resource(_load_json(path), source_paths=(path,))

    @app.get("/api/reports")
    def reports() -> dict[str, object]:
        items = []
        source_paths = []
        for report_id, (label, relative_path) in REPORT_ALLOWLIST.items():
            path = root / relative_path
            source_paths.append(path)
            items.append(
                {
                    "report_id": report_id,
                    "label": label,
                    "relative_path": relative_path,
                    "kind": path.suffix.removeprefix(".") or "directory",
                    "exists": path.is_file(),
                    "updated_at": _path_updated_at(path),
                }
            )
        return _resource(
            {"reports": items},
            source_paths=tuple(source_paths),
            available=any(item["exists"] for item in items),
        )

    return app


def _resource(
    data: Any,
    *,
    source_paths: tuple[Path, ...],
    available: bool | None = None,
) -> dict[str, object]:
    has_data = _has_data(data) if available is None else available
    return {
        "availability": "available" if has_data else "missing",
        "generated_at": _latest_updated_at(source_paths),
        "data": data,
    }


def _has_data(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_has_data(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_has_data(item) for item in value)
    return value not in (None, "", False)


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _latest_updated_at(paths: tuple[Path, ...]) -> str | None:
    timestamps = [path.stat().st_mtime for path in paths if path.is_file()]
    if not timestamps:
        return None
    return datetime.fromtimestamp(max(timestamps), tz=timezone.utc).isoformat()


def _path_updated_at(path: Path) -> str | None:
    if not path.is_file():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _sanitize_local_paths(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _sanitize_local_paths(item)
            for key, item in value.items()
            if key != "output_dir" and key != "path" and not key.endswith("_path")
        }
    if isinstance(value, list):
        return [_sanitize_local_paths(item) for item in value]
    return value
