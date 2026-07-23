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

    def index_zh_a_hist(self, *, symbol, period, start_date, end_date):
        self.calls.append((symbol, period, start_date, end_date))
        return FakeDataFrame(
            [
                (
                    0,
                    {
                        "日期": "2026-07-21",
                        "开盘": "4610.1",
                        "收盘": "4620.0",
                        "最高": "4630.5",
                        "最低": "4600.2",
                        "成交量": "123456",
                        "成交额": "987654321",
                        "涨跌幅": "0.52%",
                    },
                ),
                (
                    1,
                    {
                        "日期": "2026-07-22",
                        "开盘": "4620.0",
                        "收盘": "4652.8",
                        "最高": "4660.0",
                        "最低": "4612.0",
                        "成交量": "130000",
                        "成交额": "1000000000",
                        "涨跌幅": "0.71",
                    },
                ),
                (2, {"日期": "", "收盘": "4660"}),
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

    assert ak.calls == [("000300", "daily", "20260721", "20260722")]
    assert len(points) == 2
    assert points[-1].symbol == "000300"
    assert points[-1].close == 4652.8
    assert points[-1].change_pct == 0.71
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
    def index_zh_a_hist(self, **kwargs):
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
