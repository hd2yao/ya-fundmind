from pathlib import Path

from fund_agent.config import load_portfolio_config, load_watchlist_config


def test_watchlist_config_loads_fund_codes(tmp_path):
    path = tmp_path / "watchlist.yaml"
    path.write_text(
        """
name: Core Watchlist
funds:
  - code: 510300
    name: 沪深300ETF
  - code: 000834
    name: 广发纳斯达克100ETF联接A
""",
        encoding="utf-8",
    )

    watchlist = load_watchlist_config(path)

    assert watchlist.name == "Core Watchlist"
    assert watchlist.codes == ("510300", "000834")


def test_portfolio_config_loads_holdings(tmp_path):
    path = tmp_path / "portfolio.yaml"
    path.write_text(
        """
name: Example Portfolio
cash_available: 2000
holdings:
  - code: 510300
    name: 沪深300ETF
    shares: 800
    cost_nav: 3.7
    buy_date: 2026-02-10
    target_weight: 0.35
    notes: 核心宽基 ETF
""",
        encoding="utf-8",
    )

    portfolio = load_portfolio_config(path)

    assert portfolio.name == "Example Portfolio"
    assert portfolio.cash_available == 2000
    assert len(portfolio.holdings) == 1
    assert portfolio.holdings[0].code == "510300"
    assert portfolio.holdings[0].shares == 800
    assert portfolio.holdings[0].target_weight == 0.35
