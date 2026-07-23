from __future__ import annotations

import pytest

from fund_agent.cache import FundCache
from fund_agent.providers import AkshareProvider, ProviderUnavailable


class FakeDataFrame:
    def __init__(self, rows):
        self._rows = rows

    def iterrows(self):
        return iter(self._rows)


class BadRow:
    def get(self, key):
        raise ValueError(f"bad field: {key}")


class HistoryAkshare:
    __version__ = "9.9.9"

    def __init__(self):
        self.calls = []

    def fund_open_fund_info_em(self, *, symbol, indicator):
        self.calls.append((symbol, indicator))
        return FakeDataFrame(
            [
                (
                    0,
                    {
                        "净值日期": "2026-07-18",
                        "单位净值": "1.0200",
                        "日增长率": "0.50%",
                    },
                ),
                (
                    1,
                    {
                        "净值日期": "2026-07-21",
                        "单位净值": "1.0500",
                        "累计净值": "1.2500",
                        "日增长率": "2.94",
                    },
                ),
                (2, {"净值日期": "", "单位净值": "1.0600"}),
                (3, BadRow()),
            ]
        )


def test_akshare_history_maps_rows_filters_dates_and_writes_cache(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    ak = HistoryAkshare()
    provider = AkshareProvider(
        ak_module=ak,
        cache=cache,
        cache_ttl_days=2,
    )

    points = provider.fetch_nav_history(
        " 021511 ",
        start_date="2026-07-20",
        end_date="2026-07-22",
        as_of="2026-07-22",
    )

    assert ak.calls == [("021511", "单位净值走势")]
    assert len(points) == 1
    assert points[0].code == "021511"
    assert points[0].date == "2026-07-21"
    assert points[0].unit_nav == 1.05
    assert points[0].accumulated_nav == 1.25
    assert points[0].daily_return == 2.94
    assert points[0].source == "akshare"
    assert points[0].metadata["provider"] == "akshare"
    assert points[0].metadata["as_of"] == "2026-07-22"
    assert points[0].metadata["stale"] is False

    cached = cache.load_nav_points(code="021511")
    assert len(cached) == 1
    assert cached[0].source == "cache:akshare"
    assert cached[0].unit_nav == 1.05

    health = provider.last_health
    assert health is not None
    assert health.provider == "akshare"
    assert health.provider_version == "9.9.9"
    assert health.live_row_count == 4
    assert health.mapped_row_count == 1
    assert health.skipped_row_count == 2
    assert health.cache_write_count == 1
    assert health.endpoints[0].endpoint == "fund_open_fund_info_em"
    assert health.endpoints[0].success is True
    assert any(warning.code == "skipped_rows" for warning in health.warnings)


class FailingHistoryAkshare:
    def fund_open_fund_info_em(self, *, symbol, indicator):
        raise RuntimeError("history endpoint down")


def test_akshare_history_raises_clear_error_without_fabricating_data(tmp_path):
    provider = AkshareProvider(
        ak_module=FailingHistoryAkshare(),
        cache=FundCache(tmp_path / "funds.sqlite"),
    )

    with pytest.raises(ProviderUnavailable, match="history endpoint down"):
        provider.fetch_nav_history("021511", as_of="2026-07-22")

    health = provider.last_health
    assert health is not None
    assert health.live_row_count == 0
    assert health.mapped_row_count == 0
    assert health.cache_write_count == 0
    assert health.endpoints[0].success is False
    assert health.warnings[0].code == "live_fetch_error"


class EmptyHistoryAkshare:
    def fund_open_fund_info_em(self, *, symbol, indicator):
        return FakeDataFrame([])


def test_akshare_history_rejects_empty_response(tmp_path):
    provider = AkshareProvider(
        ak_module=EmptyHistoryAkshare(),
        cache=FundCache(tmp_path / "funds.sqlite"),
    )

    with pytest.raises(ProviderUnavailable, match="no valid NAV rows"):
        provider.fetch_nav_history("021511", as_of="2026-07-22")

    assert provider.last_health is not None
    assert provider.last_health.warnings[0].code == "empty_live_response"
