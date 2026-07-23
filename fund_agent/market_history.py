from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Protocol

from .cache import FundCache
from .models import MarketSeriesPoint
from .providers import ProviderUnavailable


INDEX_DEFINITIONS = {
    "000001": "上证指数",
    "000300": "沪深300",
    "399006": "创业板指",
}

WINDOW_POINTS = {
    "1m": 20,
    "3m": 60,
    "6m": 120,
    "1y": 240,
    "all": None,
}


class MarketHistoryUnavailable(RuntimeError):
    """Raised when neither live nor cached market history can be served."""


class MarketHistoryProvider(Protocol):
    def fetch_index_history(
        self,
        symbol: str,
        *,
        name: str,
        start_date: str | None = None,
        end_date: str | None = None,
        as_of: str | None = None,
    ) -> list[MarketSeriesPoint]:
        """Return normalized index history."""


class MarketHistoryService:
    def __init__(
        self,
        *,
        cache: FundCache,
        provider: MarketHistoryProvider,
        cache_ttl_days: int = 1,
        allow_stale_fallback: bool = True,
    ):
        self.cache = cache
        self.provider = provider
        self.cache_ttl_days = cache_ttl_days
        self.allow_stale_fallback = allow_stale_fallback

    def get_index_history(
        self,
        symbol: str,
        *,
        window: str = "6m",
        now: datetime | None = None,
    ) -> dict[str, object]:
        resolved_symbol = str(symbol).strip()
        if resolved_symbol not in INDEX_DEFINITIONS:
            raise ValueError(f"Unsupported index symbol: {resolved_symbol}")
        if window not in WINDOW_POINTS:
            raise ValueError(f"Unsupported history window: {window}")

        current_time = _utc_now(now)
        fresh = self.cache.load_market_series(
            symbol=resolved_symbol,
            series_type="index",
            source="akshare",
            now=current_time,
        )
        fresh = _index_cache_points(fresh)
        if fresh:
            return _build_payload(
                resolved_symbol,
                fresh,
                window=window,
                fallback_used=False,
                fallback_reason=None,
            )

        try:
            history_start = (current_time - timedelta(days=365 * 5)).strftime(
                "%Y%m%d"
            )
            live_points = self.provider.fetch_index_history(
                resolved_symbol,
                name=INDEX_DEFINITIONS[resolved_symbol],
                start_date=history_start,
                end_date=current_time.strftime("%Y%m%d"),
                as_of=current_time.date().isoformat(),
            )
        except ProviderUnavailable as exc:
            stale: list[MarketSeriesPoint] = []
            if self.allow_stale_fallback:
                stale = self.cache.load_market_series(
                    symbol=resolved_symbol,
                    series_type="index",
                    source="akshare",
                    allow_stale=True,
                    now=current_time,
                )
                stale = _index_cache_points(stale)
            if not stale:
                raise MarketHistoryUnavailable(
                    f"Index history is unavailable for {resolved_symbol}: {exc}"
                ) from exc
            return _build_payload(
                resolved_symbol,
                stale,
                window=window,
                fallback_used=True,
                fallback_reason=str(exc),
            )

        if not live_points:
            raise MarketHistoryUnavailable(
                f"Index history is unavailable for {resolved_symbol}: "
                "provider returned no rows"
            )
        expires_at = current_time + timedelta(days=self.cache_ttl_days)
        normalized_points = [
            replace(
                point,
                symbol=resolved_symbol,
                name=INDEX_DEFINITIONS[resolved_symbol],
                series_type="index",
                source="akshare",
                updated_at=point.updated_at or current_time.isoformat(),
                metadata={
                    **point.metadata,
                    "provider": "akshare",
                    "series_kind": "market_index_history",
                    "as_of": current_time.date().isoformat(),
                    "updated_at": point.updated_at or current_time.isoformat(),
                    "expires_at": point.metadata.get(
                        "expires_at",
                        expires_at.isoformat(),
                    ),
                    "stale": False,
                    "history_horizon": "5y",
                },
            )
            for point in live_points
        ]
        self.cache.upsert_market_series(
            normalized_points,
            as_of=current_time.date().isoformat(),
            ttl_days=self.cache_ttl_days,
            now=current_time,
        )
        return _build_payload(
            resolved_symbol,
            normalized_points,
            window=window,
            fallback_used=False,
            fallback_reason=None,
        )


def _index_cache_points(
    points: list[MarketSeriesPoint],
) -> list[MarketSeriesPoint]:
    return [
        point
        for point in points
        if point.metadata.get("series_kind") == "market_index_history"
    ]


def _build_payload(
    symbol: str,
    points: list[MarketSeriesPoint],
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
                "message": fallback_reason or "Live index history failed; cache fallback used.",
            }
        )
    if stale:
        warnings.append(
            {
                "code": "stale_cache",
                "severity": "warning",
                "message": "Index history is served from expired cache.",
            }
        )
    if insufficient:
        warnings.append(
            {
                "code": "insufficient_history",
                "severity": "warning",
                "message": (
                    f"Only {len(selected)} valid points are available; "
                    f"{required_points} are required for {window}."
                ),
            }
        )
    metadata = latest.metadata
    return {
        "symbol": symbol,
        "name": INDEX_DEFINITIONS[symbol],
        "series_type": "index",
        "range": window,
        "point_count": len(selected),
        "required_points": required_points,
        "points": [
            {
                "date": point.date,
                "open": point.open,
                "close": point.close,
                "high": point.high,
                "low": point.low,
                "volume": point.volume,
                "turnover": point.turnover,
                "change_pct": point.change_pct,
                "source": point.source,
            }
            for point in selected
        ],
        "source": latest.source,
        "as_of": latest.date,
        "updated_at": latest.updated_at or metadata.get("updated_at"),
        "expires_at": metadata.get("expires_at"),
        "stale": stale,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "data_quality_grade": "warning" if stale or insufficient else "normal",
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
