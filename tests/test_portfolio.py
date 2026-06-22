from fund_agent.models import FundRecord, ValuationResult
from fund_agent.portfolio import PortfolioHolding, analyze_portfolio


def test_portfolio_computes_value_return_and_weight_drift():
    holdings = [
        PortfolioHolding(
            code="000001",
            name="稳健成长混合A",
            shares=1000,
            cost_nav=1.0,
            buy_date="2026-01-01",
            target_weight=0.30,
        ),
        PortfolioHolding(
            code="510300",
            name="沪深300ETF",
            shares=100,
            cost_nav=2.0,
            buy_date="2026-02-01",
            target_weight=0.70,
        ),
    ]
    valuations = {
        "000001": ValuationResult(
            fund=FundRecord(code="000001", name="稳健成长混合A", category="混合型", nav=1.2),
            method="nav_only",
            estimated_value=1.2,
            confidence="Low",
        ),
        "510300": ValuationResult(
            fund=FundRecord(code="510300", name="沪深300ETF", category="ETF", price=2.0, exchange_traded=True),
            method="etf_price",
            estimated_value=2.0,
            confidence="High",
        ),
    }

    summary = analyze_portfolio(holdings, valuations)

    assert summary.total_value == 1400
    first = summary.positions[0]
    assert first.current_value == 1200
    assert first.unrealized_return_pct == 20.0
    assert first.weight > 0.85
    assert first.target_drift > 0.55


def test_portfolio_flags_concentration_and_stale_data():
    holding = PortfolioHolding(
        code="000001",
        name="稳健成长混合A",
        shares=1000,
        cost_nav=1.0,
        buy_date="2026-01-01",
        target_weight=0.40,
    )
    valuation = ValuationResult(
        fund=FundRecord(
            code="000001",
            name="稳健成长混合A",
            category="混合型",
            nav=1.2,
            nav_date="2026-06-01",
        ),
        method="nav_only",
        estimated_value=1.2,
        confidence="Low",
    )

    summary = analyze_portfolio(
        [holding],
        {"000001": valuation},
        as_of="2026-06-22",
        max_stale_days=5,
        concentration_limit=0.50,
    )

    messages = [issue.message for issue in summary.risk_issues]
    assert any("集中度" in message for message in messages)
    assert any("数据陈旧" in message for message in messages)
