from pathlib import Path

import pytest

from fund_agent.cache import FundCache
from fund_agent.providers import (
    AkshareProvider,
    EastmoneyProvider,
    FixtureProvider,
    ProviderUnavailable,
    TiantianFundProvider,
    _fund_from_akshare_row,
    load_portfolio_file,
    normalize_fund_category,
    normalize_fund_code,
    normalize_fund_name,
)


def test_fixture_provider_loads_sample_funds_without_network():
    provider = FixtureProvider(Path("data/fixtures/funds.json"))

    funds = provider.fetch_funds()

    codes = {fund.code for fund in funds}
    assert "510300" in codes
    assert "000311" in codes
    assert any(fund.proxy_symbol == "nasdaq100" for fund in funds)


def test_portfolio_file_loads_holdings():
    holdings = load_portfolio_file(Path("data/portfolio.example.json"))

    assert len(holdings) >= 2
    assert holdings[0].code
    assert holdings[0].shares > 0
    assert holdings[0].cost_nav > 0


def test_provider_normalization_helpers_clean_core_fields():
    assert normalize_fund_code(" 510300.OF ") == "510300"
    assert normalize_fund_name("  沪深300ETF  ") == "沪深300ETF"
    assert normalize_fund_category("") == "基金"


def test_akshare_row_mapping_normalizes_known_fields():
    row = {
        "基金代码": " 000311 ",
        "基金简称": " 华夏沪深300ETF联接A ",
        "基金类型": " ETF联接 ",
        "单位净值": "1.42",
        "日期": "2026-06-21 15:00:00",
        "估值日期": "2026-06-22",
        "近1周": "0.9%",
        "近1月": "2.8%",
        "近3月": "7.1%",
        "近6月": "11.2%",
        "近1年": "17.1%",
        "规模": "88.0",
    }

    fund = _fund_from_akshare_row(row)

    assert fund.code == "000311"
    assert fund.name == "华夏沪深300ETF联接A"
    assert fund.category == "ETF联接"
    assert fund.nav == 1.42
    assert fund.nav_date == "2026-06-21"
    assert fund.valuation_date == "2026-06-22"
    assert fund.returns["1m"] == 2.8
    assert fund.scale_billion == 88.0
    assert fund.source == "akshare"


def test_akshare_provider_falls_back_to_stale_cache_when_live_fails(tmp_path):
    class FailingAkshare:
        def fund_open_fund_rank_em(self, symbol):
            raise RuntimeError("network down")

    cache = FundCache(tmp_path / "funds.sqlite")
    cache.upsert_funds(
        [FixtureProvider(Path("data/fixtures/funds.json")).fetch_funds()[0]],
        as_of="2026-06-22",
        ttl_days=-1,
    )
    provider = AkshareProvider(
        ak_module=FailingAkshare(),
        cache=cache,
        allow_stale_cache=True,
    )

    funds = provider.fetch_funds()

    assert funds
    assert funds[0].source == "cache:fixture"
    assert funds[0].metadata["stale"] is True
    assert "network down" in funds[0].metadata["fallback_reason"]


def test_future_providers_raise_clear_unavailable_errors():
    with pytest.raises(ProviderUnavailable, match="EastmoneyProvider"):
        EastmoneyProvider().fetch_funds()
    with pytest.raises(ProviderUnavailable, match="TiantianFundProvider"):
        TiantianFundProvider().fetch_funds()
