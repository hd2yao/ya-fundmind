from fund_agent.models import FundNavPoint
from fund_agent.nav_summary import build_nav_history_summary, build_nav_history_windows_summary


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


def test_nav_history_summary_generates_requested_windows():
    points = [
        FundNavPoint(code="510300", date="2025-06-23", unit_nav=0.9, accumulated_nav=0.9, source="tiantian"),
        FundNavPoint(code="510300", date="2025-12-23", unit_nav=1.0, accumulated_nav=1.0, source="tiantian"),
        FundNavPoint(code="510300", date="2026-03-23", unit_nav=1.1, accumulated_nav=1.1, source="tiantian"),
        FundNavPoint(code="510300", date="2026-05-23", unit_nav=1.2, accumulated_nav=1.2, source="tiantian"),
        FundNavPoint(code="510300", date="2026-06-23", unit_nav=1.25, accumulated_nav=1.25, source="tiantian"),
    ]

    summary = build_nav_history_windows_summary(
        "510300",
        points,
        windows=("1m", "3m", "6m", "1y", "all"),
        as_of="2026-06-23",
    )

    assert set(summary["windows"]) == {"1m", "3m", "6m", "1y", "all"}
    assert summary["windows"]["1m"]["start_date"] == "2026-05-23"
    assert summary["windows"]["3m"]["start_date"] == "2026-03-23"
    assert summary["windows"]["6m"]["start_date"] == "2025-12-23"
    assert summary["windows"]["1y"]["start_date"] == "2025-06-23"
    assert summary["windows"]["all"]["count"] == 5
    assert summary["windows_requested"] == ["1m", "3m", "6m", "1y", "all"]


def test_nav_history_summary_marks_short_window_annualized_return_unstable():
    points = [
        FundNavPoint(code="510300", date="2026-06-22", unit_nav=1.0, source="tiantian"),
        FundNavPoint(code="510300", date="2026-06-23", unit_nav=1.1, source="tiantian"),
    ]

    summary = build_nav_history_windows_summary("510300", points, windows=("1m",), as_of="2026-06-23")
    window = summary["windows"]["1m"]

    assert window["data_quality_grade"] in {"warning", "degraded"}
    assert window["metadata"]["annualized_return_unstable"] is True
    assert "短样本" in window["metadata"]["annualized_return_note"]
