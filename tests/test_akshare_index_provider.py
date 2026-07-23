from __future__ import annotations

import pytest

from fund_agent.cache import FundCache
from fund_agent.providers import AkshareProvider, ProviderUnavailable


class FakeDataFrame:
    def __init__(self, rows):
        self.rows = rows

    def iterrows(self):
        return iter(self.rows)


class IndexAkshare:
    __version__ = "9.9.9"

    def __init__(self):
        self.calls = []

    def stock_zh_index_daily_em(self, *, symbol, start_date, end_date):
        self.calls.append((symbol, start_date, end_date))
        return FakeDataFrame(
            [
                (
                    0,
                    {
                        "date": "2026-07-21",
                        "open": "4610.1",
                        "close": "4620.0",
                        "high": "4630.5",
                        "low": "4600.2",
                        "volume": "123456",
                        "amount": "987654321",
                    },
                ),
                (
                    1,
                    {
                        "date": "2026-07-22",
                        "open": "4620.0",
                        "close": "4652.8",
                        "high": "4660.0",
                        "low": "4612.0",
                        "volume": "130000",
                        "amount": "1000000000",
                    },
                ),
                (2, {"date": "", "close": "4660"}),
            ]
        )


def test_akshare_index_history_maps_rows_and_writes_cache(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    ak = IndexAkshare()
    provider = AkshareProvider(ak_module=ak, cache=cache, cache_ttl_days=2)

    points = provider.fetch_index_history(
        "000300",
        name="沪深300",
        start_date="20260721",
        end_date="20260722",
        as_of="2026-07-22",
    )

    assert ak.calls == [("sh000300", "20260721", "20260722")]
    assert len(points) == 2
    assert points[-1].symbol == "000300"
    assert points[-1].close == 4652.8
    assert points[-1].change_pct == pytest.approx(0.71, abs=0.005)
    assert points[-1].metadata["series_kind"] == "market_index_history"
    cached = cache.load_market_series(
        symbol="000300",
        series_type="index",
        source="akshare",
    )
    assert len(cached) == 2
    assert provider.last_health is not None
    assert provider.last_health.live_row_count == 3
    assert provider.last_health.mapped_row_count == 2
    assert provider.last_health.skipped_row_count == 1
    assert provider.last_health.cache_write_count == 2


class InvalidIndexAkshare:
    def stock_zh_index_daily_em(self, **kwargs):
        return {"unexpected": "shape"}


def test_akshare_index_history_rejects_invalid_response(tmp_path):
    provider = AkshareProvider(
        ak_module=InvalidIndexAkshare(),
        cache=FundCache(tmp_path / "funds.sqlite"),
    )

    with pytest.raises(ProviderUnavailable, match="no valid index rows"):
        provider.fetch_index_history(
            "000300",
            name="沪深300",
            as_of="2026-07-22",
        )

    assert provider.last_health is not None
    assert any(
        warning.code == "invalid_response"
        for warning in provider.last_health.warnings
    )


class FallbackIndexAkshare:
    def stock_zh_index_daily_em(self, **kwargs):
        raise RuntimeError("eastmoney unavailable")

    def stock_zh_index_daily(self, *, symbol):
        return FakeDataFrame(
            [
                (
                    0,
                    {
                        "date": "2026-07-22",
                        "open": 4620.0,
                        "close": 4652.8,
                        "high": 4660.0,
                        "low": 4612.0,
                        "volume": 130000,
                    },
                )
            ]
        )


def test_akshare_index_history_falls_back_to_sina_endpoint(tmp_path):
    provider = AkshareProvider(
        ak_module=FallbackIndexAkshare(),
        cache=FundCache(tmp_path / "funds.sqlite"),
    )

    points = provider.fetch_index_history(
        "000300",
        name="沪深300",
        start_date="20260701",
        end_date="20260722",
        as_of="2026-07-22",
    )

    assert len(points) == 1
    assert points[0].close == 4652.8
    assert provider.last_health is not None
    assert [item.endpoint for item in provider.last_health.endpoints] == [
        "stock_zh_index_daily_em",
        "stock_zh_index_daily",
    ]
    assert provider.last_health.endpoints[0].success is False
    assert provider.last_health.endpoints[1].success is True
    assert any(
        warning.code == "endpoint_fallback"
        for warning in provider.last_health.warnings
    )
