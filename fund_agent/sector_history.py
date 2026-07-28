from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from math import ceil
from typing import Protocol

from .cache import FundCache
from .market_history import WINDOW_POINTS
from .models import MarketEntity, MarketSeriesPoint
from .providers import ProviderUnavailable


INDUSTRY_SYMBOL_PATTERN = re.compile(r"^BK\d{4}$")
FULL_HISTORY_START = "19900101"


class MarketSectorUnavailable(RuntimeError):
    """Raised when neither live nor cached industry data can be served."""


class MarketSectorProvider(Protocol):
    def fetch_industry_boards(
        self,
        *,
        as_of: str | None = None,
    ) -> list[MarketEntity]:
        """Return normalized industry board catalog rows."""

    def fetch_industry_history(
        self,
        symbol: str,
        *,
        name: str,
        start_date: str | None = None,
        end_date: str | None = None,
        as_of: str | None = None,
    ) -> list[MarketSeriesPoint]:
        """Return normalized industry board history."""


@dataclass(frozen=True)
class _CatalogResult:
    entities: list[MarketEntity]
    fallback_used: bool
    fallback_reason: str | None


class MarketSectorService:
    def __init__(
        self,
        *,
        cache: FundCache,
        provider: MarketSectorProvider,
        cache_ttl_days: int = 1,
        allow_stale_fallback: bool = True,
    ):
        self.cache = cache
        self.provider = provider
        self.cache_ttl_days = cache_ttl_days
        self.allow_stale_fallback = allow_stale_fallback

    def search_sectors(
        self,
        *,
        q: str = "",
        page: int = 1,
        page_size: int = 25,
        now: datetime | None = None,
    ) -> dict[str, object]:
        if page < 1:
            raise ValueError("page must be at least 1")
        if page_size < 1 or page_size > 100:
            raise ValueError("page_size must be between 1 and 100")
        current_time = _utc_now(now)
        catalog = self._load_catalog(current_time)
        normalized_query = q.strip().casefold()
        filtered = [
            entity
            for entity in catalog.entities
            if not normalized_query
            or normalized_query in entity.symbol.casefold()
            or normalized_query in entity.name.casefold()
        ]
        filtered.sort(
            key=lambda entity: (
                -(entity.change_pct if entity.change_pct is not None else -10_000),
                entity.symbol,
            )
        )
        total = len(filtered)
        start = (page - 1) * page_size
        selected = filtered[start : start + page_size]
        stale = any(
            bool(entity.metadata.get("stale"))
            for entity in catalog.entities
        )
        reference = catalog.entities[0] if catalog.entities else None
        warnings = _fallback_warnings(
            fallback_used=catalog.fallback_used,
            fallback_reason=catalog.fallback_reason,
            stale=stale,
            resource_name="Industry catalog",
        )
        return {
            "items": [_entity_payload(entity) for entity in selected],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": ceil(total / page_size) if total else 0,
            "query": q.strip(),
            "sort": "change_pct_desc",
            "source": reference.source if reference else None,
            "as_of": max(
                (
                    entity.as_of
                    for entity in catalog.entities
                    if entity.as_of
                ),
                default=None,
            ),
            "updated_at": (
                reference.updated_at
                or reference.metadata.get("updated_at")
                if reference
                else None
            ),
            "expires_at": (
                reference.metadata.get("expires_at") if reference else None
            ),
            "stale": stale,
            "fallback_used": catalog.fallback_used,
            "fallback_reason": catalog.fallback_reason,
            "data_quality_grade": (
                "warning" if stale or catalog.fallback_used else "normal"
            ),
            "warnings": warnings,
            "not_production_model": True,
            "main_score_changed": False,
            "main_risk_changed": False,
        }

    def get_sector_history(
        self,
        symbol: str,
        *,
        window: str = "6m",
        now: datetime | None = None,
        as_of: str | None = None,
        force_refresh: bool = False,
    ) -> dict[str, object]:
        resolved_symbol = str(symbol).strip().upper()
        if not INDUSTRY_SYMBOL_PATTERN.fullmatch(resolved_symbol):
            raise ValueError(f"Unsupported industry symbol: {resolved_symbol}")
        if window not in WINDOW_POINTS:
            raise ValueError(f"Unsupported history window: {window}")
        current_time = _utc_now(now)
        requested_as_of = _resolve_as_of_date(as_of, current_time)
        catalog = self._load_catalog(current_time)
        entity = next(
            (
                item
                for item in catalog.entities
                if item.symbol == resolved_symbol
            ),
            None,
        )
        if entity is None:
            raise ValueError(f"Unknown industry symbol: {resolved_symbol}")

        fresh = _industry_cache_points(
            self.cache.load_market_series(
                symbol=resolved_symbol,
                series_type="industry",
                source="akshare",
                now=current_time,
            )
        )
        if fresh and not force_refresh and (
            window != "all" or _has_complete_history_horizon(fresh)
        ):
            return _build_history_payload(
                entity,
                fresh,
                window=window,
                fallback_used=False,
                fallback_reason=None,
            )

        try:
            history_horizon = "all" if window == "all" else "5y"
            history_start = (
                FULL_HISTORY_START
                if history_horizon == "all"
                else (requested_as_of - timedelta(days=365 * 5)).strftime(
                    "%Y%m%d"
                )
            )
            live_points = self.provider.fetch_industry_history(
                resolved_symbol,
                name=entity.name,
                start_date=history_start,
                end_date=requested_as_of.strftime("%Y%m%d"),
                as_of=requested_as_of.isoformat(),
            )
        except ProviderUnavailable as exc:
            stale: list[MarketSeriesPoint] = []
            if self.allow_stale_fallback:
                stale = _industry_cache_points(
                    self.cache.load_market_series(
                        symbol=resolved_symbol,
                        series_type="industry",
                        source="akshare",
                        allow_stale=True,
                        now=current_time,
                    )
                )
            if not stale:
                raise MarketSectorUnavailable(
                    f"Industry history is unavailable for "
                    f"{resolved_symbol}: {exc}"
                ) from exc
            return _build_history_payload(
                entity,
                stale,
                window=window,
                fallback_used=True,
                fallback_reason=str(exc),
            )

        if not live_points:
            raise MarketSectorUnavailable(
                f"Industry history is unavailable for {resolved_symbol}: "
                "provider returned no rows"
            )
        expires_at = current_time + timedelta(days=self.cache_ttl_days)
        normalized_points = [
            replace(
                point,
                symbol=resolved_symbol,
                name=entity.name,
                series_type="industry",
                source="akshare",
                updated_at=point.updated_at or current_time.isoformat(),
                metadata={
                    **point.metadata,
                    "provider": "akshare",
                    "series_kind": "market_industry_history",
                    "as_of": requested_as_of.isoformat(),
                    "updated_at": point.updated_at or current_time.isoformat(),
                    "expires_at": point.metadata.get(
                        "expires_at",
                        expires_at.isoformat(),
                    ),
                    "stale": False,
                    "history_horizon": history_horizon,
                },
            )
            for point in live_points
        ]
        self.cache.upsert_market_series(
            normalized_points,
            as_of=requested_as_of.isoformat(),
            ttl_days=self.cache_ttl_days,
            now=current_time,
        )
        return _build_history_payload(
            entity,
            normalized_points,
            window=window,
            fallback_used=False,
            fallback_reason=None,
        )

    def refresh_sector_histories(
        self,
        symbols: list[str],
        *,
        now: datetime | None = None,
        as_of: str | None = None,
    ) -> dict[str, object]:
        """Refresh explicit industry histories without failing the whole batch."""

        current_time = _utc_now(now)
        resolved_symbols = _normalize_sector_symbols(symbols)
        sectors: list[dict[str, object]] = []
        warnings: list[dict[str, str]] = []

        for symbol in resolved_symbols:
            try:
                payload = self.get_sector_history(
                    symbol,
                    window="all",
                    now=current_time,
                    as_of=as_of,
                    force_refresh=True,
                )
            except (MarketSectorUnavailable, ValueError) as exc:
                message = str(exc)
                sectors.append(
                    {
                        "symbol": symbol,
                        "name": None,
                        "status": "unavailable",
                        "source": None,
                        "as_of": None,
                        "updated_at": None,
                        "expires_at": None,
                        "stale": False,
                        "fallback_used": False,
                        "warnings": [
                            {
                                "code": "sector_refresh_unavailable",
                                "severity": "warning",
                                "message": message,
                            }
                        ],
                    }
                )
                warnings.append(
                    {
                        "code": "sector_refresh_unavailable",
                        "severity": "warning",
                        "symbol": symbol,
                        "message": f"{symbol}: {message}",
                    }
                )
                continue

            fallback_used = bool(payload["fallback_used"])
            sectors.append(
                {
                    "symbol": payload["symbol"],
                    "name": payload["name"],
                    "status": "fallback" if fallback_used else "success",
                    "source": payload["source"],
                    "as_of": payload["as_of"],
                    "updated_at": payload["updated_at"],
                    "expires_at": payload["expires_at"],
                    "stale": payload["stale"],
                    "fallback_used": fallback_used,
                    "warnings": payload["warnings"],
                }
            )
            if fallback_used:
                warnings.append(
                    {
                        "code": "sector_refresh_fallback",
                        "severity": "warning",
                        "symbol": str(payload["symbol"]),
                        "message": (
                            f"{payload['symbol']} {payload['name']}: "
                            "live refresh failed; cache fallback used."
                        ),
                    }
                )

        return {
            "generated_at": current_time.isoformat(),
            "sectors": sectors,
            "success_count": sum(item["status"] == "success" for item in sectors),
            "fallback_count": sum(item["status"] == "fallback" for item in sectors),
            "unavailable_count": sum(item["status"] == "unavailable" for item in sectors),
            "warnings": warnings,
            "not_production_model": True,
            "main_score_changed": False,
            "main_risk_changed": False,
        }

    def _load_catalog(self, current_time: datetime) -> _CatalogResult:
        fresh = self.cache.load_market_entities(
            entity_type="industry",
            source="akshare",
            now=current_time,
        )
        if fresh:
            return _CatalogResult(
                entities=fresh,
                fallback_used=False,
                fallback_reason=None,
            )
        try:
            live = self.provider.fetch_industry_boards(
                as_of=current_time.date().isoformat()
            )
        except ProviderUnavailable as exc:
            stale: list[MarketEntity] = []
            if self.allow_stale_fallback:
                stale = self.cache.load_market_entities(
                    entity_type="industry",
                    source="akshare",
                    allow_stale=True,
                    now=current_time,
                )
            if not stale:
                raise MarketSectorUnavailable(
                    f"Industry catalog is unavailable: {exc}"
                ) from exc
            return _CatalogResult(
                entities=stale,
                fallback_used=True,
                fallback_reason=str(exc),
            )
        if not live:
            raise MarketSectorUnavailable(
                "Industry catalog is unavailable: provider returned no rows"
            )
        expires_at = current_time + timedelta(days=self.cache_ttl_days)
        normalized = [
            replace(
                entity,
                entity_type="industry",
                source="akshare",
                as_of=entity.as_of or current_time.date().isoformat(),
                updated_at=entity.updated_at or current_time.isoformat(),
                metadata={
                    **entity.metadata,
                    "provider": "akshare",
                    "as_of": entity.as_of or current_time.date().isoformat(),
                    "updated_at": entity.updated_at or current_time.isoformat(),
                    "expires_at": entity.metadata.get(
                        "expires_at",
                        expires_at.isoformat(),
                    ),
                    "stale": False,
                },
            )
            for entity in live
        ]
        self.cache.upsert_market_entities(
            normalized,
            as_of=current_time.date().isoformat(),
            ttl_days=self.cache_ttl_days,
            now=current_time,
        )
        return _CatalogResult(
            entities=normalized,
            fallback_used=False,
            fallback_reason=None,
        )


def _entity_payload(entity: MarketEntity) -> dict[str, object]:
    return {
        "symbol": entity.symbol,
        "name": entity.name,
        "entity_type": entity.entity_type,
        "latest": entity.latest,
        "change_pct": entity.change_pct,
        "market_cap": entity.market_cap,
        "turnover_rate": entity.turnover_rate,
        "rise_count": entity.rise_count,
        "fall_count": entity.fall_count,
        "leader_name": entity.leader_name,
        "leader_change_pct": entity.leader_change_pct,
        "source": entity.source,
        "as_of": entity.as_of,
        "updated_at": entity.updated_at or entity.metadata.get("updated_at"),
        "expires_at": entity.metadata.get("expires_at"),
        "stale": bool(entity.metadata.get("stale")),
    }


def _industry_cache_points(
    points: list[MarketSeriesPoint],
) -> list[MarketSeriesPoint]:
    return [
        point
        for point in points
        if point.metadata.get("series_kind")
        == "market_industry_history"
    ]


def _has_complete_history_horizon(
    points: list[MarketSeriesPoint],
) -> bool:
    return bool(points) and all(
        point.metadata.get("history_horizon") == "all"
        for point in points
    )


def _build_history_payload(
    entity: MarketEntity,
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
    history_horizon = latest.metadata.get("history_horizon")
    partial_history = window == "all" and history_horizon != "all"
    warnings = _fallback_warnings(
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        stale=stale,
        resource_name="Industry history",
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
    if partial_history:
        warnings.append(
            {
                "code": "partial_history",
                "severity": "warning",
                "message": (
                    "Complete industry history is unavailable; "
                    "the all range contains only cached partial history."
                ),
            }
        )
    metadata = latest.metadata
    return {
        "symbol": entity.symbol,
        "name": entity.name,
        "series_type": "industry",
        "range": window,
        "point_count": len(selected),
        "required_points": required_points,
        "history_horizon": history_horizon or "partial",
        "points": [
            {
                "date": point.date,
                "open": point.open,
                "close": point.close,
                "high": point.high,
                "low": point.low,
                "volume": point.volume,
                "turnover": point.turnover,
                "turnover_rate": point.metadata.get("turnover_rate"),
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
        "data_quality_grade": (
            "warning"
            if stale or insufficient or fallback_used or partial_history
            else "normal"
        ),
        "warnings": warnings,
        "not_production_model": True,
        "main_score_changed": False,
        "main_risk_changed": False,
    }


def _fallback_warnings(
    *,
    fallback_used: bool,
    fallback_reason: str | None,
    stale: bool,
    resource_name: str,
) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if fallback_used:
        warnings.append(
            {
                "code": "live_fallback",
                "severity": "warning",
                "message": (
                    fallback_reason
                    or f"Live {resource_name.lower()} failed; cache fallback used."
                ),
            }
        )
    if stale:
        warnings.append(
            {
                "code": "stale_cache",
                "severity": "warning",
                "message": f"{resource_name} is served from expired cache.",
            }
        )
    return warnings


def _normalize_sector_symbols(symbols: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        value = str(symbol).strip().upper()
        if not INDUSTRY_SYMBOL_PATTERN.fullmatch(value):
            raise ValueError(f"Unsupported industry symbol: {value}")
        if value not in seen:
            seen.add(value)
            normalized.append(value)
    if not normalized:
        raise ValueError("At least one industry symbol is required.")
    return normalized


def _resolve_as_of_date(value: str | None, current_time: datetime) -> date:
    if not value:
        return current_time.date()
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            "--as-of must be an ISO date, for example 2026-07-28."
        ) from exc


def _utc_now(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
