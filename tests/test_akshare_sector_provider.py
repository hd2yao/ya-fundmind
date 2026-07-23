from __future__ import annotations

import pytest

from fund_agent.cache import FundCache
from fund_agent.providers import AkshareProvider, ProviderUnavailable


class FakeDataFrame:
    def __init__(self, rows):
        self.rows = rows

    def iterrows(self):
        return iter(self.rows)


class SectorAkshare:
    __version__ = "9.9.9"

    def __init__(self):
        self.catalog_calls = 0
        self.history_calls = []

    def stock_board_industry_name_em(self):
        self.catalog_calls += 1
        return FakeDataFrame(
            [
                (
                    0,
                    {
                        "板块代码": "BK1036",
                        "板块名称": "半导体",
                        "最新价": "1823.40",
                        "涨跌幅": "2.31%",
                        "总市值": "345,678,901",
                        "换手率": "3.25%",
                        "上涨家数": "41",
                        "下跌家数": "6",
                        "领涨股票": "示例股份",
                        "领涨股票-涨跌幅": "9.98%",
                    },
                ),
                (
                    1,
                    {
                        "板块代码": "BK0475",
                        "板块名称": "银行",
                        "最新价": 1022.5,
                        "涨跌幅": -0.4,
                    },
                ),
                (2, {"板块代码": "", "板块名称": "缺少代码"}),
            ]
        )

    def stock_board_industry_hist_em(
        self,
        *,
        symbol,
        start_date,
        end_date,
        period,
        adjust,
    ):
        self.history_calls.append(
            (symbol, start_date, end_date, period, adjust)
        )
        return FakeDataFrame(
            [
                (
                    0,
                    {
                        "日期": "2026-07-21",
                        "开盘": "1800.0",
                        "收盘": "1810.0",
                        "最高": "1820.0",
                        "最低": "1795.0",
                        "成交量": "123456",
                        "成交额": "987654321",
                        "涨跌幅": "0.56",
                        "换手率": "2.10",
                    },
                ),
                (
                    1,
                    {
                        "日期": "2026-07-22",
                        "开盘": "1810.0",
                        "收盘": "1823.4",
                        "最高": "1830.0",
                        "最低": "1802.0",
                        "成交量": "130000",
                        "成交额": "1000000000",
                        "涨跌幅": "0.74",
                        "换手率": "2.30",
                    },
                ),
                (2, {"日期": "", "收盘": "1825.0"}),
            ]
        )


def test_akshare_industry_catalog_maps_rows_and_writes_cache(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    ak = SectorAkshare()
    provider = AkshareProvider(ak_module=ak, cache=cache, cache_ttl_days=2)

    entities = provider.fetch_industry_boards(as_of="2026-07-23")

    assert ak.catalog_calls == 1
    assert len(entities) == 2
    assert entities[0].symbol == "BK1036"
    assert entities[0].name == "半导体"
    assert entities[0].latest == 1823.4
    assert entities[0].change_pct == 2.31
    assert entities[0].turnover_rate == 3.25
    assert entities[0].rise_count == 41
    assert entities[0].leader_name == "示例股份"
    cached = cache.load_market_entities(
        entity_type="industry",
        source="akshare",
    )
    assert len(cached) == 2
    assert provider.last_health is not None
    assert provider.last_health.live_row_count == 3
    assert provider.last_health.mapped_row_count == 2
    assert provider.last_health.skipped_row_count == 1
    assert provider.last_health.cache_write_count == 2
    assert provider.last_health.endpoints[0].endpoint == "stock_board_industry_name_em"


def test_akshare_industry_history_maps_rows_and_writes_cache(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    ak = SectorAkshare()
    provider = AkshareProvider(ak_module=ak, cache=cache, cache_ttl_days=2)

    points = provider.fetch_industry_history(
        "BK1036",
        name="半导体",
        start_date="20260721",
        end_date="20260722",
        as_of="2026-07-23",
    )

    assert ak.history_calls == [
        ("BK1036", "20260721", "20260722", "日k", "")
    ]
    assert len(points) == 2
    assert points[-1].series_type == "industry"
    assert points[-1].close == 1823.4
    assert points[-1].turnover == 1000000000.0
    assert points[-1].metadata["turnover_rate"] == 2.3
    assert points[-1].metadata["series_kind"] == "market_industry_history"
    cached = cache.load_market_series(
        symbol="BK1036",
        series_type="industry",
        source="akshare",
    )
    assert len(cached) == 2
    assert provider.last_health is not None
    assert provider.last_health.live_row_count == 3
    assert provider.last_health.mapped_row_count == 2
    assert provider.last_health.skipped_row_count == 1
    assert provider.last_health.cache_write_count == 2


class InvalidSectorAkshare:
    def stock_board_industry_name_em(self):
        return {"unexpected": "shape"}

    def stock_board_industry_hist_em(self, **kwargs):
        return FakeDataFrame([(0, {"日期": "", "收盘": ""})])


def test_akshare_industry_catalog_rejects_invalid_response(tmp_path):
    provider = AkshareProvider(
        ak_module=InvalidSectorAkshare(),
        cache=FundCache(tmp_path / "funds.sqlite"),
    )

    with pytest.raises(ProviderUnavailable, match="no valid industry rows"):
        provider.fetch_industry_boards(as_of="2026-07-23")

    assert provider.last_health is not None
    assert any(
        warning.code == "invalid_response"
        for warning in provider.last_health.warnings
    )


def test_akshare_industry_history_rejects_all_bad_rows(tmp_path):
    provider = AkshareProvider(
        ak_module=InvalidSectorAkshare(),
        cache=FundCache(tmp_path / "funds.sqlite"),
    )

    with pytest.raises(ProviderUnavailable, match="no valid industry history"):
        provider.fetch_industry_history(
            "BK1036",
            name="半导体",
            as_of="2026-07-23",
        )

    assert provider.last_health is not None
    assert provider.last_health.skipped_row_count == 1
