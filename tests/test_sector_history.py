from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from fund_agent.cache import FundCache
from fund_agent.models import MarketEntity, MarketSeriesPoint, ProviderEndpointTrace, ProviderHealth
from fund_agent.providers import AkshareProvider, ProviderUnavailable
from fund_agent.sector_history import MarketSectorService, MarketSectorUnavailable


NOW = datetime(2026, 7, 23, tzinfo=timezone.utc)


def _entities() -> list[MarketEntity]:
    return [
        MarketEntity(
            symbol="BK1036",
            name="半导体",
            entity_type="industry",
            latest=1823.4,
            change_pct=2.31,
            source="akshare",
            as_of="2026-07-23",
            metadata={"endpoint": "stock_board_industry_name_em"},
        ),
        MarketEntity(
            symbol="BK0475",
            name="银行",
            entity_type="industry",
            latest=1022.5,
            change_pct=-0.4,
            source="akshare",
            as_of="2026-07-23",
            metadata={"endpoint": "stock_board_industry_name_em"},
        ),
    ]


def _points(count: int = 25) -> list[MarketSeriesPoint]:
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    return [
        MarketSeriesPoint(
            symbol="BK1036",
            name="半导体",
            series_type="industry",
            date=(start + timedelta(days=index)).date().isoformat(),
            close=1800.0 + index,
            change_pct=0.1,
            source="akshare",
            metadata={"series_kind": "market_industry_history"},
        )
        for index in range(count)
    ]


def _complete_points(count: int = 25) -> list[MarketSeriesPoint]:
    return [
        replace(
            point,
            metadata={
                **point.metadata,
                "history_horizon": "all",
            },
        )
        for point in _points(count)
    ]


class NeverLiveProvider:
    def fetch_industry_boards(self, **kwargs):
        raise AssertionError("fresh catalog cache should prevent live access")

    def fetch_industry_history(self, *args, **kwargs):
        raise AssertionError("fresh history cache should prevent live access")


def test_sector_search_uses_fresh_catalog_cache_and_filters_query(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    cache.upsert_market_entities(
        _entities(),
        as_of="2026-07-23",
        ttl_days=2,
        now=NOW,
    )
    service = MarketSectorService(cache=cache, provider=NeverLiveProvider())

    payload = service.search_sectors(q="BK1036", page=1, page_size=10, now=NOW)

    assert payload["total"] == 1
    assert payload["items"][0]["name"] == "半导体"
    assert payload["source"] == "cache:akshare"
    assert payload["stale"] is False
    assert payload["fallback_used"] is False


class LiveProvider:
    def __init__(self):
        self.catalog_calls = 0
        self.history_calls = []

    def fetch_industry_boards(self, **kwargs):
        self.catalog_calls += 1
        return _entities()

    def fetch_industry_history(self, symbol, **kwargs):
        self.history_calls.append((symbol, kwargs))
        return _points(25)


def test_sector_search_fetches_live_writes_cache_and_paginates(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    provider = LiveProvider()
    service = MarketSectorService(cache=cache, provider=provider)

    payload = service.search_sectors(page=1, page_size=1, now=NOW)

    assert provider.catalog_calls == 1
    assert payload["total"] == 2
    assert payload["total_pages"] == 2
    assert payload["items"][0]["symbol"] == "BK1036"
    assert len(
        cache.load_market_entities(
            entity_type="industry",
            source="akshare",
            now=NOW,
        )
    ) == 2


class FailingProvider:
    def fetch_industry_boards(self, **kwargs):
        raise ProviderUnavailable("catalog network down")

    def fetch_industry_history(self, symbol, **kwargs):
        raise ProviderUnavailable("history network down")


class PartiallyAvailableHistoryProvider(LiveProvider):
    def fetch_industry_history(self, symbol, **kwargs):
        self.history_calls.append((symbol, kwargs))
        if symbol == "BK0475":
            raise ProviderUnavailable("bank history unavailable")
        return _points(25)


class HealthRecordingHistoryProvider(LiveProvider):
    def fetch_industry_history(self, symbol, **kwargs):
        self.last_health = ProviderHealth(
            provider="akshare",
            provider_version="9.9.9",
            started_at=NOW.isoformat(),
            finished_at=NOW.isoformat(),
            duration_ms=1,
            live_row_count=25,
            mapped_row_count=25,
            cache_write_count=25,
            endpoints=(
                ProviderEndpointTrace(
                    endpoint="stock_board_industry_hist_em",
                    started_at=NOW.isoformat(),
                    finished_at=NOW.isoformat(),
                    duration_ms=1,
                ),
            ),
        )
        return super().fetch_industry_history(symbol, **kwargs)


class EmptyHistoryPreservesPreviousHealth(HealthRecordingHistoryProvider):
    def fetch_industry_history(self, symbol, **kwargs):
        if symbol == "BK0475":
            self.history_calls.append((symbol, kwargs))
            return []
        return super().fetch_industry_history(symbol, **kwargs)


def test_sector_search_falls_back_to_stale_catalog(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    cache.upsert_market_entities(
        _entities(),
        as_of="2026-07-20",
        ttl_days=1,
        now=NOW - timedelta(days=3),
    )
    service = MarketSectorService(cache=cache, provider=FailingProvider())

    payload = service.search_sectors(now=NOW)

    assert payload["stale"] is True
    assert payload["fallback_used"] is True
    assert payload["data_quality_grade"] == "warning"
    assert any(
        warning["code"] == "live_fallback"
        for warning in payload["warnings"]
    )


def test_sector_search_fails_without_live_or_cache(tmp_path):
    service = MarketSectorService(
        cache=FundCache(tmp_path / "funds.sqlite"),
        provider=FailingProvider(),
    )

    with pytest.raises(MarketSectorUnavailable, match="catalog network down"):
        service.search_sectors(now=NOW)


def test_sector_history_uses_fresh_cache_and_applies_window(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    cache.upsert_market_entities(
        _entities(),
        as_of="2026-07-23",
        ttl_days=2,
        now=NOW,
    )
    cache.upsert_market_series(
        _points(25),
        as_of="2026-07-23",
        ttl_days=2,
        now=NOW,
    )
    service = MarketSectorService(cache=cache, provider=NeverLiveProvider())

    payload = service.get_sector_history(
        "BK1036",
        window="1m",
        now=NOW,
    )

    assert payload["symbol"] == "BK1036"
    assert payload["name"] == "半导体"
    assert payload["series_type"] == "industry"
    assert payload["point_count"] == 20
    assert payload["source"] == "cache:akshare"


def test_sector_history_fetches_live_and_writes_cache(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    provider = LiveProvider()
    service = MarketSectorService(cache=cache, provider=provider)

    payload = service.get_sector_history(
        "BK1036",
        window="all",
        now=NOW,
    )

    assert provider.catalog_calls == 1
    assert len(provider.history_calls) == 1
    assert provider.history_calls[0][0] == "BK1036"
    assert provider.history_calls[0][1]["start_date"] == "19900101"
    assert provider.history_calls[0][1]["end_date"] == "20260723"
    assert payload["point_count"] == 25
    assert len(
        cache.load_market_series(
            symbol="BK1036",
            series_type="industry",
            source="akshare",
            now=NOW,
        )
    ) == 25


def test_sector_history_all_refetches_when_fresh_cache_is_partial(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    cache.upsert_market_entities(
        _entities(),
        as_of="2026-07-23",
        ttl_days=2,
        now=NOW,
    )
    cache.upsert_market_series(
        _points(25),
        as_of="2026-07-23",
        ttl_days=2,
        now=NOW,
    )
    provider = LiveProvider()
    service = MarketSectorService(cache=cache, provider=provider)

    payload = service.get_sector_history("BK1036", window="all", now=NOW)

    assert len(provider.history_calls) == 1
    assert provider.history_calls[0][1]["start_date"] == "19900101"
    assert payload["history_horizon"] == "all"


def test_sector_history_all_uses_complete_fresh_cache(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    cache.upsert_market_entities(
        _entities(),
        as_of="2026-07-23",
        ttl_days=2,
        now=NOW,
    )
    cache.upsert_market_series(
        _complete_points(25),
        as_of="2026-07-23",
        ttl_days=2,
        now=NOW,
    )
    service = MarketSectorService(cache=cache, provider=NeverLiveProvider())

    payload = service.get_sector_history("BK1036", window="all", now=NOW)

    assert payload["point_count"] == 25
    assert payload["history_horizon"] == "all"


def test_sector_history_falls_back_to_stale_cache(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    cache.upsert_market_entities(
        _entities(),
        as_of="2026-07-20",
        ttl_days=10,
        now=NOW - timedelta(days=3),
    )
    cache.upsert_market_series(
        _points(5),
        as_of="2026-07-20",
        ttl_days=1,
        now=NOW - timedelta(days=3),
    )
    service = MarketSectorService(cache=cache, provider=FailingProvider())

    payload = service.get_sector_history(
        "BK1036",
        window="all",
        now=NOW,
    )

    assert payload["stale"] is True
    assert payload["fallback_used"] is True
    assert any(
        warning["code"] == "stale_cache"
        for warning in payload["warnings"]
    )
    assert any(
        warning["code"] == "partial_history"
        for warning in payload["warnings"]
    )


def test_sector_history_refreshes_explicit_symbols_and_continues_after_failure(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    provider = PartiallyAvailableHistoryProvider()
    service = MarketSectorService(cache=cache, provider=provider)

    payload = service.refresh_sector_histories(
        ["BK1036", "BK0475"],
        now=NOW,
        as_of="2026-07-23",
    )

    assert [item["symbol"] for item in payload["sectors"]] == [
        "BK1036",
        "BK0475",
    ]
    assert payload["success_count"] == 1
    assert payload["fallback_count"] == 0
    assert payload["unavailable_count"] == 1
    assert payload["sectors"][0]["status"] == "success"
    assert payload["sectors"][1]["status"] == "unavailable"
    assert len(payload["provider_health"]) == 2
    assert payload["provider_health"][0]["sector_symbol"] == "BK1036"
    assert payload["provider_health"][1]["sector_symbol"] == "BK0475"
    assert payload["provider_health"][1]["warnings"]
    assert len(
        cache.load_market_series(
            symbol="BK1036",
            series_type="industry",
            source="akshare",
            now=NOW,
        )
    ) == 25


def test_sector_history_refresh_unknown_symbol_does_not_reuse_previous_health(tmp_path):
    provider = HealthRecordingHistoryProvider()
    service = MarketSectorService(
        cache=FundCache(tmp_path / "funds.sqlite"),
        provider=provider,
    )

    payload = service.refresh_sector_histories(
        ["BK1036", "BK9999"],
        now=NOW,
        as_of="2026-07-23",
    )

    previous, unknown = payload["provider_health"]
    assert previous["sector_symbol"] == "BK1036"
    assert previous["live_row_count"] == 25
    assert unknown["sector_symbol"] == "BK9999"
    assert unknown["live_row_count"] == 0
    assert unknown["mapped_row_count"] == 0
    assert unknown["cache_write_count"] == 0
    assert unknown["endpoints"] == []


def test_sector_history_refresh_unavailable_provider_does_not_reuse_previous_health(tmp_path):
    provider = EmptyHistoryPreservesPreviousHealth()
    service = MarketSectorService(
        cache=FundCache(tmp_path / "funds.sqlite"),
        provider=provider,
    )

    payload = service.refresh_sector_histories(
        ["BK1036", "BK0475"],
        now=NOW,
        as_of="2026-07-23",
    )

    previous, unavailable = payload["provider_health"]
    assert previous["sector_symbol"] == "BK1036"
    assert previous["live_row_count"] == 25
    assert unavailable["sector_symbol"] == "BK0475"
    assert unavailable["live_row_count"] == 0
    assert unavailable["endpoints"] == []


def test_sector_search_missing_akshare_method_uses_stale_cache(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    cache.upsert_market_entities(
        _entities(),
        as_of="2026-07-20",
        ttl_days=1,
        now=NOW - timedelta(days=3),
    )
    provider = AkshareProvider(ak_module=object(), cache=cache)
    service = MarketSectorService(cache=cache, provider=provider)

    payload = service.search_sectors(now=NOW)

    assert payload["fallback_used"] is True
    assert payload["stale"] is True
    assert "endpoint is unavailable" in payload["fallback_reason"]


@pytest.mark.parametrize(
    "symbol,window",
    [("1036", "6m"), ("BK9999", "6m"), ("BK1036", "2y")],
)
def test_sector_history_rejects_invalid_or_unknown_request(
    tmp_path,
    symbol,
    window,
):
    cache = FundCache(tmp_path / "funds.sqlite")
    cache.upsert_market_entities(
        _entities(),
        as_of="2026-07-23",
        ttl_days=2,
        now=NOW,
    )
    service = MarketSectorService(cache=cache, provider=NeverLiveProvider())

    with pytest.raises(ValueError):
        service.get_sector_history(symbol, window=window, now=NOW)
