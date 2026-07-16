from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import __version__
from .review_state import VALID_REVIEW_STATUSES, list_review_state, summarize_review_state
from .web_console import (
    build_copilot_view_model,
    build_web_console_state,
    run_copilot_for_web,
    update_review_state_for_web,
)


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


class CopilotRequest(BaseModel):
    question: str = Field(max_length=1000)


class ReviewUpdateRequest(BaseModel):
    status: str = Field(max_length=80)
    note: str = Field(default="", max_length=2000)
    reviewer: str = Field(default="", max_length=120)
    signal_id: str | None = Field(default=None, max_length=200)


def create_web_app(
    *,
    output_dir: Path | str = Path("outputs"),
    review_state_path: Path | str | None = None,
    static_dir: Path | str | None = None,
) -> FastAPI:
    """Build the local product Web Console API with fixed filesystem roots."""

    root = Path(output_dir).expanduser().resolve()
    state_path = (
        Path(review_state_path).expanduser().resolve()
        if review_state_path is not None
        else root / "manual_review_state.json"
    )
    static_root = Path(static_dir).expanduser().resolve() if static_dir is not None else None
    app = FastAPI(
        title="YA FundMind OS Local API",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.output_dir = root
    app.state.review_state_path = state_path
    app.state.static_dir = static_root

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

    @app.get("/api/reports/{report_id}")
    def open_report(report_id: str):
        report = REPORT_ALLOWLIST.get(report_id)
        if report is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "report_not_allowed", "message": "Report is not in the allowlist."},
            )
        path = root / report[1]
        if not path.is_file():
            raise HTTPException(
                status_code=404,
                detail={"code": "report_missing", "message": "Report has not been generated."},
            )
        return FileResponse(path)

    @app.post("/api/copilot/ask")
    def ask_copilot(request: CopilotRequest) -> dict[str, object]:
        question = request.question.strip()
        if not question:
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid_question", "message": "Research question must not be blank."},
            )
        try:
            answer = run_copilot_for_web(question=question, output_dir=root)
        except Exception as exc:  # pragma: no cover - endpoint boundary protection
            raise HTTPException(
                status_code=500,
                detail={"code": "copilot_failed", "message": type(exc).__name__},
            ) from exc
        payload = asdict(answer)
        answer_path = root / "copilot" / "research_answer.json"
        return _resource(
            {
                "answer": payload,
                "view_model": build_copilot_view_model(payload),
            },
            source_paths=(answer_path,),
            available=True,
        )

    @app.get("/api/reviews")
    def reviews() -> dict[str, object]:
        queue_path = root / "manual_review_queue.json"
        queue = _load_json(queue_path)
        if not isinstance(queue, list):
            queue = []
        state = list_review_state(state_path)
        return _resource(
            {
                "queue": queue,
                "state": state,
                "summary": summarize_review_state(state),
            },
            source_paths=(queue_path, state_path),
            available=bool(queue or state),
        )

    @app.post("/api/reviews/{review_id}")
    def update_review(review_id: str, request: ReviewUpdateRequest) -> dict[str, object]:
        if request.status not in VALID_REVIEW_STATUSES:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_review_status",
                    "message": f"Unsupported review status: {request.status}",
                },
            )
        queue = _load_json(root / "manual_review_queue.json")
        queue_items = queue if isinstance(queue, list) else []
        state_items = list_review_state(state_path)
        known_ids = {
            str(item.get("review_id"))
            for item in [*queue_items, *state_items]
            if isinstance(item, dict) and item.get("review_id")
        }
        if review_id not in known_ids:
            raise HTTPException(
                status_code=404,
                detail={"code": "review_not_found", "message": "Review item does not exist."},
            )
        item = update_review_state_for_web(
            review_state_path=state_path,
            review_id=review_id,
            status=request.status,
            note=request.note,
            reviewer=request.reviewer,
            signal_id=request.signal_id,
        )
        return _resource(item, source_paths=(state_path,), available=True)

    if static_root is not None:
        index_path = static_root / "index.html"

        @app.get("/{requested_path:path}")
        def serve_spa(requested_path: str):
            if requested_path == "api" or requested_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not Found")
            candidate = (static_root / requested_path).resolve()
            if candidate.is_relative_to(static_root) and candidate.is_file():
                return FileResponse(candidate)
            if index_path.is_file():
                return FileResponse(index_path)
            raise HTTPException(status_code=404, detail="Product web build is missing.")

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
