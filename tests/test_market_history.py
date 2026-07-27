from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from fund_agent.cache import FundCache
from fund_agent.market_history import MarketHistoryService, MarketHistoryUnavailable
from fund_agent.models import MarketSeriesPoint
from fund_agent.providers import ProviderUnavailable


def _points(count: int = 25) -> list[MarketSeriesPoint]:
    return [
        MarketSeriesPoint(
            symbol="000300",
            name="沪深300",
            series_type="index",
            date=f"2026-06-{index + 1:02d}",
            close=4500.0 + index,
            change_pct=0.1,
            source="akshare",
            metadata={"series_kind": "market_index_history"},
        )
        for index in range(count)
    ]


class NeverLiveProvider:
    def fetch_index_history(self, *args, **kwargs):
        raise AssertionError("fresh cache should prevent live access")


def test_market_history_uses_fresh_cache_and_applies_window(tmp_path):
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    cache = FundCache(tmp_path / "funds.sqlite")
    cache.upsert_market_series(
        _points(25),
        as_of="2026-07-01",
        ttl_days=2,
        now=now,
    )
    service = MarketHistoryService(cache=cache, provider=NeverLiveProvider())

    payload = service.get_index_history("000300", window="1m", now=now)

    assert payload["symbol"] == "000300"
    assert payload["name"] == "沪深300"
    assert payload["point_count"] == 20
    assert payload["source"] == "cache:akshare"
    assert payload["as_of"] == "2026-06-25"


class LiveProvider:
    def __init__(self):
        self.calls = []

    def fetch_index_history(self, symbol, **kwargs):
        self.calls.append((symbol, kwargs))
        return _points(25)


def test_market_history_fetches_live_and_writes_cache(tmp_path):
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    cache = FundCache(tmp_path / "funds.sqlite")
    provider = LiveProvider()
    service = MarketHistoryService(cache=cache, provider=provider)

    payload = service.get_index_history("000300", window="all", now=now)

    assert len(provider.calls) == 1
    assert provider.calls[0][1]["start_date"] == "20210702"
    assert provider.calls[0][1]["end_date"] == "20260701"
    assert payload["point_count"] == 25
    assert payload["source"] == "akshare"
    assert len(
        cache.load_market_series(
            symbol="000300",
            series_type="index",
            source="akshare",
            now=now,
        )
    ) == 25


def test_market_history_force_refreshes_fresh_cache_and_keeps_sync_metadata(tmp_path):
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    cache = FundCache(tmp_path / "funds.sqlite")
    cache.upsert_market_series(
        _points(25),
        as_of="2026-06-30",
        ttl_days=2,
        now=now - timedelta(hours=1),
    )
    provider = LiveProvider()
    service = MarketHistoryService(cache=cache, provider=provider)

    payload = service.get_index_history(
        "000300",
        window="all",
        now=now,
        force_refresh=True,
    )

    assert len(provider.calls) == 1
    assert payload["source"] == "akshare"
    assert payload["as_of"] == "2026-06-25"
    assert payload["updated_at"] == now.isoformat()
    assert payload["expires_at"] == (now + timedelta(days=1)).isoformat()


class PartialRefreshProvider:
    def __init__(self):
        self.calls = []

    def fetch_index_history(self, symbol, **kwargs):
        self.calls.append((symbol, kwargs))
        if symbol == "399006":
            raise ProviderUnavailable("index endpoint unavailable")
        return [
            MarketSeriesPoint(
                symbol=symbol,
                name=kwargs["name"],
                series_type="index",
                date="2026-07-01",
                close=4000.0,
                change_pct=0.2,
                source="akshare",
                metadata={"series_kind": "market_index_history"},
            )
        ]


def test_market_history_refreshes_allowlisted_indices_without_stopping_on_one_failure(tmp_path):
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    provider = PartialRefreshProvider()
    service = MarketHistoryService(
        cache=FundCache(tmp_path / "funds.sqlite"),
        provider=provider,
    )

    payload = service.refresh_index_histories(now=now)

    assert [item["symbol"] for item in payload["indices"]] == [
        "000001",
        "000300",
        "399006",
    ]
    assert [item["status"] for item in payload["indices"]] == [
        "success",
        "success",
        "unavailable",
    ]
    assert payload["success_count"] == 2
    assert payload["unavailable_count"] == 1
    assert payload["generated_at"] == now.isoformat()
    assert any(item["symbol"] == "399006" for item in payload["warnings"])
    assert [symbol for symbol, _kwargs in provider.calls] == [
        "000001",
        "000300",
        "399006",
    ]


class FailingProvider:
    def fetch_index_history(self, symbol, **kwargs):
        raise ProviderUnavailable("network down")


def test_market_history_falls_back_to_stale_cache(tmp_path):
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    cache = FundCache(tmp_path / "funds.sqlite")
    cache.upsert_market_series(
        _points(5),
        as_of="2026-06-01",
        ttl_days=1,
        now=now - timedelta(days=10),
    )
    service = MarketHistoryService(cache=cache, provider=FailingProvider())

    payload = service.get_index_history("000300", window="all", now=now)

    assert payload["stale"] is True
    assert payload["fallback_used"] is True
    assert payload["data_quality_grade"] == "warning"
    assert any(item["code"] == "live_fallback" for item in payload["warnings"])


@pytest.mark.parametrize("symbol,window", [("123456", "6m"), ("000300", "2y")])
def test_market_history_validates_allowlist_and_window(tmp_path, symbol, window):
    service = MarketHistoryService(
        cache=FundCache(tmp_path / "funds.sqlite"),
        provider=NeverLiveProvider(),
    )

    with pytest.raises(ValueError):
        service.get_index_history(symbol, window=window)


def test_market_history_fails_without_live_or_cache(tmp_path):
    service = MarketHistoryService(
        cache=FundCache(tmp_path / "funds.sqlite"),
        provider=FailingProvider(),
    )

    with pytest.raises(MarketHistoryUnavailable, match="network down"):
        service.get_index_history("000300")
