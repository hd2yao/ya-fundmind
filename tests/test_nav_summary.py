from fund_agent.models import FundNavPoint
from fund_agent.nav_summary import build_nav_history_summary


def test_nav_history_summary_computes_observation_metrics():
    points = [
        FundNavPoint(code="510300", date="2026-06-20", unit_nav=1.0, accumulated_nav=1.0, source="tiantian"),
        FundNavPoint(code="510300", date="2026-06-21", unit_nav=1.1, accumulated_nav=1.1, source="tiantian"),
        FundNavPoint(code="510300", date="2026-06-22", unit_nav=1.05, accumulated_nav=1.05, source="tiantian"),
    ]

    summary = build_nav_history_summary("510300", points)

    assert summary["count"] == 3
    assert summary["start_date"] == "2026-06-20"
    assert summary["end_date"] == "2026-06-22"
    assert summary["latest_unit_nav"] == 1.05
    assert summary["latest_accumulated_nav"] == 1.05
    assert summary["total_return"] == 5.0
    assert summary["max_drawdown"] == -4.5455
    assert summary["volatility"] is not None
    assert summary["source"] == "tiantian"
    assert summary["data_quality_grade"] == "normal"


def test_nav_history_summary_degrades_empty_or_sparse_history():
    summary = build_nav_history_summary("510300", [])

    assert summary["count"] == 0
    assert summary["data_quality_grade"] == "degraded"
