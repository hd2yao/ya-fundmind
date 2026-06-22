from fund_agent.models import FundRecord
from fund_agent.valuation import classify_valuation, estimate_value


def test_exchange_traded_etf_uses_market_price():
    fund = FundRecord(
        code="510300",
        name="沪深300ETF",
        category="ETF",
        nav=4.01,
        price=4.05,
        exchange_traded=True,
    )

    result = estimate_value(fund)

    assert result.method == "etf_price"
    assert result.estimated_value == 4.05
    assert result.confidence == "High"


def test_etf_feeder_is_classified_from_target_etf():
    fund = FundRecord(
        code="000311",
        name="华夏沪深300ETF联接A",
        category="ETF联接",
        nav=1.42,
        target_etf="510300",
    )

    assert classify_valuation(fund) == "feeder"
    assert estimate_value(fund).confidence == "Medium"


def test_qdii_uses_proxy_when_available():
    fund = FundRecord(
        code="000834",
        name="广发纳斯达克100ETF联接A",
        category="QDII",
        nav=2.35,
        proxy_symbol="nasdaq100",
    )

    result = estimate_value(fund)

    assert result.method == "qdii_proxy"
    assert "nasdaq100" in result.notes


def test_open_fund_falls_back_to_latest_nav():
    fund = FundRecord(
        code="110022",
        name="易方达消费行业股票",
        category="股票型",
        nav=4.12,
    )

    result = estimate_value(fund)

    assert result.method == "nav_only"
    assert result.estimated_value == 4.12
    assert result.confidence == "Low"


def test_missing_price_and_nav_is_unsupported():
    fund = FundRecord(code="999999", name="未知基金", category="未知")

    result = estimate_value(fund)

    assert result.method == "unsupported"
    assert result.estimated_value is None
    assert result.confidence == "Needs checking"
