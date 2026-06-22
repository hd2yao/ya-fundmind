from pathlib import Path
from dataclasses import replace

from fund_agent.agents import run_research
from fund_agent.providers import FixtureProvider, load_portfolio_file
from fund_agent.report import render_html, render_markdown


def test_research_run_combines_ranking_valuation_and_portfolio_risk():
    funds = FixtureProvider(Path("data/fixtures/funds.json")).fetch_funds()
    holdings = load_portfolio_file(Path("data/portfolio.example.json"))

    result = run_research(funds, holdings=holdings, as_of="2026-06-22")

    assert result.ranked_candidates
    assert result.valuations["510300"].confidence == "High"
    assert result.portfolio is not None
    assert result.portfolio.risk_issues
    assert any(candidate.evidence_label in {"Medium", "Needs checking"} for candidate in result.ranked_candidates)


def test_markdown_and_html_reports_include_risk_boundary_and_evidence():
    funds = FixtureProvider(Path("data/fixtures/funds.json")).fetch_funds()
    holdings = load_portfolio_file(Path("data/portfolio.example.json"))
    result = run_research(funds, holdings=holdings, as_of="2026-06-22")

    markdown = render_markdown(result)
    html = render_html(result)

    assert "不构成投资建议" in markdown
    assert "研究优先级" in markdown
    assert "证据" in markdown
    assert "估值方式" in markdown
    assert "风险提示" in markdown
    assert "<html" in html
    assert "不构成投资建议" in html


def test_markdown_report_includes_snapshot_delta_when_available():
    funds = FixtureProvider(Path("data/fixtures/funds.json")).fetch_funds()
    result = run_research(funds, as_of="2026-06-22")
    result = replace(
        result,
        snapshot_delta={
            "previous_as_of": "2026-06-21",
            "score_changes": [{"code": "510300", "name": "沪深300ETF", "delta": 1.5}],
            "valuation_changes": [],
            "risk_changes": {"added": [], "resolved": []},
            "holding_risk_changes": {"risk_count_delta": 0},
        },
    )

    markdown = render_markdown(result)

    assert "历史快照对比" in markdown
    assert "2026-06-21" in markdown
    assert "510300" in markdown
