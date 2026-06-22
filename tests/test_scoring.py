from fund_agent.models import FundRecord
from fund_agent.scoring import rank_funds, score_fund


def test_stable_multi_period_fund_outranks_sprint_only_fund():
    stable = FundRecord(
        code="000001",
        name="稳健成长混合A",
        category="混合型",
        nav=1.52,
        returns={"1w": 1.2, "1m": 3.5, "3m": 8.4, "6m": 15.0, "1y": 24.0},
        scale_billion=42.0,
    )
    sprint = FundRecord(
        code="000002",
        name="短期冲刺主题A",
        category="股票型",
        nav=2.01,
        returns={"1w": 8.0, "1m": 25.0, "3m": 27.0, "6m": 6.0, "1y": -4.0},
        scale_billion=38.0,
    )

    ranked = rank_funds([sprint, stable])

    assert ranked[0].fund.code == "000001"
    assert ranked[0].breakdown.anti_sprint_penalty < ranked[1].breakdown.anti_sprint_penalty


def test_negative_long_term_returns_are_penalized():
    weak = FundRecord(
        code="000003",
        name="长期回撤基金A",
        category="混合型",
        nav=0.82,
        returns={"1w": 1.0, "1m": 2.0, "3m": -6.0, "6m": -18.0, "1y": -30.0},
        scale_billion=18.0,
    )

    scored = score_fund(weak)

    assert scored.total_score < 50
    assert scored.breakdown.return_quality < 20
