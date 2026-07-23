from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .cache import FundCache
from .nav_summary import REQUIRED_NAV_POINTS_BY_WINDOW, SUPPORTED_NAV_WINDOWS
from .providers import normalize_fund_code


def build_tiantian_cache_diagnostics(
    cache: FundCache,
    *,
    code: str,
    as_of: str | None = None,
    now: datetime | None = None,
) -> dict:
    normalized_code = normalize_fund_code(code)
    details = [
        item
        for item in cache.load_fund_details(
            code=normalized_code,
            as_of=as_of,
            allow_stale=True,
            now=now,
        )
        if item.source == "cache:tiantian"
    ]
    if not details and as_of is not None:
        details = [
            item
            for item in cache.load_fund_details(
                code=normalized_code,
                allow_stale=True,
                now=now,
            )
            if item.source == "cache:tiantian"
        ]
    nav_points = [
        item
        for item in cache.load_nav_points(
            code=normalized_code,
            allow_stale=True,
            now=now,
        )
        if item.source == "cache:tiantian"
    ]
    detail_stale = any(item.metadata.get("stale") for item in details)
    nav_stale = any(item.metadata.get("stale") for item in nav_points)
    latest_nav = nav_points[-1] if nav_points else None
    warnings = []
    if detail_stale or nav_stale:
        warnings.append(
            {
                "code": "stale_cache",
                "severity": "warning",
                "message": "Tiantian cache contains stale records.",
            }
        )
    if not details:
        warnings.append(
            {
                "code": "detail_cache_miss",
                "severity": "warning",
                "message": f"No cached Tiantian fund detail found for {normalized_code}.",
            }
        )
    if not nav_points:
        warnings.append(
            {
                "code": "nav_cache_miss",
                "severity": "warning",
                "message": f"No cached Tiantian NAV history found for {normalized_code}.",
            }
        )
    return {
        "code": normalized_code,
        "detail_cache_status": _cache_status(details, detail_stale),
        "nav_cache_status": _cache_status(nav_points, nav_stale),
        "detail_source": details[-1].source if details else None,
        "nav_source": latest_nav.source if latest_nav else None,
        "nav_points_count": len(nav_points),
        "latest_nav_date": latest_nav.date if latest_nav else None,
        "available_windows": _available_windows(len(nav_points)),
        "stale": bool(detail_stale or nav_stale),
        "warnings": warnings,
    }


def write_tiantian_cache_diagnostics(payload: dict, output_dir: Path | str) -> Path:
    path = Path(output_dir) / "tiantian_cache_diagnostics.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _cache_status(items: list, stale: bool) -> str:
    if not items:
        return "miss"
    if stale:
        return "stale"
    return "hit"


def _available_windows(nav_points_count: int) -> list[str]:
    windows = [
        window
        for window in SUPPORTED_NAV_WINDOWS
        if window != "all" and nav_points_count >= REQUIRED_NAV_POINTS_BY_WINDOW[window]
    ]
    if nav_points_count:
        windows.append("all")
    return windows
