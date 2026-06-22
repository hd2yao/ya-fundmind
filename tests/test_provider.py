from pathlib import Path

from fund_agent.providers import FixtureProvider, load_portfolio_file


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
