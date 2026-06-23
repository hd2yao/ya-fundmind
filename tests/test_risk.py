from fund_agent.agents import run_research
from fund_agent.models import FundRecord, ProviderHealth, ProviderWarning
from fund_agent.portfolio import PortfolioHolding


def test_provider_quality_issues_are_added_to_risk_agent_output():
    health = ProviderHealth(
        provider="akshare",
        started_at="2026-06-23T00:00:00+00:00",
        finished_at="2026-06-23T00:00:01+00:00",
        duration_ms=1000,
        fallback_used=True,
        fallback_reason="network down",
        fallback_source="cache",
        watchlist_requested_count=2,
        watchlist_matched_count=1,
        watchlist_missing_codes=("999999",),
        warnings=(
            ProviderWarning(code="live_fallback", message="using cache", severity="warning"),
            ProviderWarning(code="stale_cache", message="expired cache", severity="critical"),
        ),
    )
    funds = [
        FundRecord(
            code="510300",
            name="沪深300ETF",
            category="ETF",
            nav=5.0,
            source="cache:akshare",
            metadata={"stale": True},
        )
    ]
    holdings = [
        PortfolioHolding(
            code="510300",
            name="沪深300ETF",
            shares=1,
            cost_nav=4.0,
            buy_date="2026-01-01",
        )
    ]

    result = run_research(
        funds,
        holdings=holdings,
        as_of="2026-06-23",
        provider_health=(health,),
    )

    assert result.portfolio is not None
    messages = [issue.message for issue in result.portfolio.risk_issues]
    assert any("fallback" in message for message in messages)
    assert any("stale" in message.lower() or "过期" in message for message in messages)
    assert any("999999" in message for message in messages)
