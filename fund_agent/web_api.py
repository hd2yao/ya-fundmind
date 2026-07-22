from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .fund_explorer import FundExplorerIndex, FundSearchQuery
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

FUND_DETAIL_ALLOWLIST = {
    "accumulated_nav",
    "data_coverage",
    "data_quality_grade",
    "data_quality_warnings",
    "fund_company",
    "fund_manager",
    "inception_date",
    "is_portfolio",
    "is_watchlist",
    "market_rank_context",
    "missing_fields",
    "nav_history_summary",
    "observation_notes",
    "peer_comparison",
    "rating",
    "return_windows",
    "signal_context",
    "unknown_reason",
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
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"],
    )
    app.state.output_dir = root
    app.state.review_state_path = state_path
    app.state.static_dir = static_root
    app.state.fund_explorer = FundExplorerIndex(
        root / "market" / "market_intelligence_report.json"
    )

    @app.middleware("http")
    async def enforce_local_write_origin(request: Request, call_next):
        if request.url.path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and not _is_loopback_origin(origin):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": {
                            "code": "cross_origin_write_forbidden",
                            "message": "Local API writes only accept loopback origins.",
                        }
                    },
                )
        return await call_next(request)

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
                "intelligence": _load_json_object(intelligence_path),
                "trend": _load_json_object(trend_path),
            },
            source_paths=(intelligence_path, trend_path),
        )

    @app.get("/api/funds")
    def funds() -> dict[str, object]:
        details_path = root / "fund_details" / "watchlist_fund_details.json"
        signals_path = root / "signal_candidates.json"
        return _resource(
            {
                "details": _load_json_object(details_path),
                "signal_candidates": _load_json_object(signals_path),
            },
            source_paths=(details_path, signals_path),
        )

    @app.get("/api/funds/search")
    def search_funds(
        q: str = Query(default="", max_length=200),
        fund_type: str | None = Query(default=None, max_length=120),
        theme: str | None = Query(default=None, max_length=120),
        exchange_traded: bool | None = None,
        quality: Literal["normal", "warning", "degraded", "unknown"] | None = None,
        sort: Literal[
            "code",
            "name",
            "return_1m",
            "return_3m",
            "return_6m",
            "return_1y",
        ] = "code",
        direction: Literal["asc", "desc"] = "asc",
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=25, ge=1, le=100),
    ) -> dict[str, object]:
        return app.state.fund_explorer.search(
            FundSearchQuery(
                q=q,
                fund_type=fund_type,
                theme=theme,
                exchange_traded=exchange_traded,
                quality=quality,
                sort=sort,
                direction=direction,
                page=page,
                page_size=page_size,
            )
        )

    @app.get("/api/funds/{code}")
    def fund_detail(code: str) -> dict[str, object]:
        if len(code) != 6 or not code.isdigit():
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid_fund_code", "message": "Fund code must be six digits."},
            )
        fund = app.state.fund_explorer.get(code)
        if fund is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "fund_not_found", "message": "Fund is not present in the market index."},
            )
        return {
            "fund": fund,
            "research_detail": _find_research_detail(root, code),
            "not_production_model": True,
            "main_score_changed": False,
            "main_risk_changed": False,
        }

    @app.get("/api/portfolio")
    def portfolio() -> dict[str, object]:
        path = root / "portfolio" / "portfolio_report.json"
        return _resource(_load_json_object(path), source_paths=(path,))

    @app.get("/api/news")
    def news() -> dict[str, object]:
        path = root / "news" / "news_evidence_report.json"
        return _resource(_load_json_object(path), source_paths=(path,))

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
        canonical_item = next(
            (
                item
                for item in [*queue_items, *state_items]
                if isinstance(item, dict) and str(item.get("review_id")) == review_id
            ),
            {},
        )
        canonical_signal_id = str(canonical_item.get("signal_id") or review_id)
        if request.signal_id and request.signal_id != canonical_signal_id:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "review_signal_mismatch",
                    "message": "Review signal_id must match the canonical queue item.",
                },
            )
        item = update_review_state_for_web(
            review_state_path=state_path,
            review_id=review_id,
            status=request.status,
            note=request.note,
            reviewer=request.reviewer,
            signal_id=canonical_signal_id,
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


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    return payload if isinstance(payload, dict) else {}


def _find_research_detail(root: Path, code: str) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    watchlist = _load_json_object(root / "fund_details" / "watchlist_fund_details.json")
    watchlist_items = watchlist.get("fund_details")
    if isinstance(watchlist_items, list):
        candidates.extend(item for item in watchlist_items if isinstance(item, dict))

    single = _load_json_object(root / "fund_details" / f"fund_detail_{code}.json")
    nested = single.get("fund_detail")
    if isinstance(nested, dict):
        candidates.append(nested)
    elif single:
        candidates.append(single)

    detail = next((item for item in candidates if str(item.get("code") or "") == code), {})
    allowed = {key: detail[key] for key in FUND_DETAIL_ALLOWLIST if key in detail}
    sanitized = _sanitize_local_paths(allowed)
    return sanitized if isinstance(sanitized, dict) else {}


def _is_loopback_origin(origin: str) -> bool:
    parsed = urlsplit(origin)
    return (
        parsed.scheme == "http"
        and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        and parsed.username is None
        and parsed.password is None
    )


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
