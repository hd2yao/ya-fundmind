from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Protocol

from .cache import FundCache
from .models import FundNavPoint
from .providers import ProviderUnavailable, normalize_fund_code


WINDOW_POINTS = {
    "1m": 20,
    "3m": 60,
    "6m": 120,
    "1y": 240,
    "all": None,
}


class FundHistoryUnavailable(RuntimeError):
    """Raised when neither live nor cached history can serve a request."""


class FundHistoryProvider(Protocol):
    def fetch_nav_history(
        self,
        code: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        as_of: str | None = None,
    ) -> list[FundNavPoint]:
        """Return normalized NAV history."""


class FundHistoryService:
    def __init__(
        self,
        *,
        cache: FundCache,
        provider: FundHistoryProvider,
        cache_ttl_days: int = 1,
        allow_stale_fallback: bool = True,
    ):
        self.cache = cache
        self.provider = provider
        self.cache_ttl_days = cache_ttl_days
        self.allow_stale_fallback = allow_stale_fallback

    def get_history(
        self,
        code: str,
        *,
        window: str = "6m",
        now: datetime | None = None,
    ) -> dict[str, object]:
        normalized_code = normalize_fund_code(code)
        if len(normalized_code) != 6 or not normalized_code.isdigit():
            raise ValueError("Fund code must be six digits.")
        if window not in WINDOW_POINTS:
            raise ValueError(f"Unsupported history window: {window}")

        current_time = _utc_now(now)
        fresh = self.cache.load_nav_points(
            code=normalized_code,
            source="akshare",
            now=current_time,
        )
        fresh = _history_cache_points(fresh)
        if fresh:
            return _build_history_payload(
                normalized_code,
                fresh,
                window=window,
                fallback_used=False,
                fallback_reason=None,
            )

        try:
            live_points = self.provider.fetch_nav_history(
                normalized_code,
                as_of=current_time.date().isoformat(),
            )
        except ProviderUnavailable as exc:
            stale = []
            if self.allow_stale_fallback:
                stale = self.cache.load_nav_points(
                    code=normalized_code,
                    source="akshare",
                    allow_stale=True,
                    now=current_time,
                )
                stale = _history_cache_points(stale)
            if not stale:
                raise FundHistoryUnavailable(
                    f"Fund history is unavailable for {normalized_code}: {exc}"
                ) from exc
            return _build_history_payload(
                normalized_code,
                stale,
                window=window,
                fallback_used=True,
                fallback_reason=str(exc),
            )

        if not live_points:
            raise FundHistoryUnavailable(
                f"Fund history is unavailable for {normalized_code}: provider returned no rows"
            )
        expires_at = current_time + timedelta(days=self.cache_ttl_days)
        normalized_points = [
            replace(
                point,
                code=normalized_code,
                source="akshare",
                updated_at=point.updated_at or current_time.isoformat(),
                metadata={
                    **point.metadata,
                    "provider": "akshare",
                    "series_kind": "fund_nav_history",
                    "as_of": current_time.date().isoformat(),
                    "updated_at": point.updated_at or current_time.isoformat(),
                    "expires_at": point.metadata.get(
                        "expires_at",
                        expires_at.isoformat(),
                    ),
                    "stale": False,
                },
            )
            for point in live_points
        ]
        self.cache.upsert_nav_points(
            normalized_points,
            as_of=current_time.date().isoformat(),
            ttl_days=self.cache_ttl_days,
            now=current_time,
        )
        return _build_history_payload(
            normalized_code,
            normalized_points,
            window=window,
            fallback_used=False,
            fallback_reason=None,
        )


def _history_cache_points(points: list[FundNavPoint]) -> list[FundNavPoint]:
    return [
        point
        for point in points
        if point.metadata.get("series_kind") == "fund_nav_history"
    ]


def _build_history_payload(
    code: str,
    points: list[FundNavPoint],
    *,
    window: str,
    fallback_used: bool,
    fallback_reason: str | None,
) -> dict[str, object]:
    ordered = sorted(points, key=lambda point: point.date)
    required_points = WINDOW_POINTS[window]
    selected = ordered if required_points is None else ordered[-required_points:]
    latest = selected[-1]
    stale = any(bool(point.metadata.get("stale")) for point in selected)
    insufficient = required_points is not None and len(selected) < required_points
    warnings: list[dict[str, str]] = []
    if fallback_used:
        warnings.append(
            {
                "code": "live_fallback",
                "severity": "warning",
                "message": fallback_reason or "Live history failed; cache fallback used.",
            }
        )
    if stale:
        warnings.append(
            {
                "code": "stale_cache",
                "severity": "warning",
                "message": "Historical NAV cache is expired.",
            }
        )
    if insufficient:
        warnings.append(
            {
                "code": "insufficient_history",
                "severity": "warning",
                "message": (
                    f"{window} requires {required_points} NAV points; "
                    f"only {len(selected)} are available."
                ),
            }
        )
    quality_grade = "warning" if stale or fallback_used or insufficient else "normal"
    metadata = latest.metadata
    return {
        "code": code,
        "range": window,
        "point_count": len(selected),
        "required_points": required_points,
        "points": [
            {
                "date": point.date,
                "unit_nav": point.unit_nav,
                "accumulated_nav": point.accumulated_nav,
                "daily_return": point.daily_return,
                "source": point.source,
            }
            for point in selected
        ],
        "source": latest.source,
        "as_of": metadata.get("cache_as_of")
        or metadata.get("as_of")
        or latest.date,
        "updated_at": metadata.get("updated_at") or latest.updated_at,
        "expires_at": metadata.get("expires_at"),
        "stale": stale,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "data_quality_grade": quality_grade,
        "warnings": warnings,
        "not_production_model": True,
        "main_score_changed": False,
        "main_risk_changed": False,
    }


def _utc_now(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
