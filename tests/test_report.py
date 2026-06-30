from pathlib import Path
from dataclasses import replace

from fund_agent.agents import run_research
from fund_agent.models import FundDetail, FundRecord, ProviderHealth, ProviderWarning
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


def test_html_report_renders_interactive_dashboard_sections():
    funds = FixtureProvider(Path("data/fixtures/funds.json")).fetch_funds()
    holdings = load_portfolio_file(Path("data/portfolio.example.json"))
    result = run_research(funds, holdings=holdings, as_of="2026-06-22")

    html = render_html(result)

    assert 'class="app-shell"' in html
    assert 'class="section-nav"' in html
    assert 'href="#research-priority"' in html
    assert '<section id="research-priority"' in html
    assert 'class="metric-card"' in html
    assert '<details class="report-panel" open>' in html
    assert '<table class="data-table">' in html
    assert "<thead>" in html
    assert "<tbody>" in html
    assert 'id="fund-510300"' in html
    assert 'data-code="510300"' in html
    assert 'class="severity severity-high"' in html
    assert "| 排名 |" not in html


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


def test_markdown_report_marks_stale_cache_data():
    result = run_research(
        [
            FundRecord(
                code="510300",
                name="沪深300ETF",
                category="ETF",
                nav=4.01,
                nav_date="2026-06-21",
                source="cache:akshare",
                metadata={"stale": True, "expires_at": "2026-06-20T00:00:00+00:00"},
            )
        ],
        as_of="2026-06-22",
    )

    markdown = render_markdown(result)

    assert "stale data" in markdown
    assert "2026-06-20" in markdown


def test_markdown_report_includes_data_freshness_table():
    result = run_research(
        [
            FundRecord(
                code="510300",
                name="沪深300ETF",
                category="ETF",
                nav=4.01,
                nav_date="2026-06-21",
                valuation_date="2026-06-22",
                source="akshare",
                metadata={
                    "as_of": "2026-06-22",
                    "updated_at": "2026-06-22T01:00:00+00:00",
                    "expires_at": "2026-06-23T01:00:00+00:00",
                    "stale": False,
                },
            )
        ],
        as_of="2026-06-22",
    )

    markdown = render_markdown(result)

    assert "数据来源与新鲜度" in markdown
    assert "akshare" in markdown
    assert "2026-06-22" in markdown
    assert "| 510300 | 沪深300ETF | akshare | 2026-06-22 |" in markdown


def test_markdown_report_includes_provider_health_and_warnings():
    health = ProviderHealth(
        provider="akshare",
        provider_version="9.9.9",
        started_at="2026-06-23T00:00:00+00:00",
        finished_at="2026-06-23T00:00:02+00:00",
        duration_ms=2000,
        live_row_count=4,
        mapped_row_count=2,
        skipped_row_count=1,
        cache_write_count=2,
        fallback_used=True,
        fallback_reason="network down",
        fallback_source="cache",
        watchlist_requested_count=2,
        watchlist_matched_count=1,
        watchlist_missing_codes=("999999",),
        warnings=(
            ProviderWarning(
                code="fallback_cache",
                message="AKShare live failed; using cache.",
                severity="warning",
            ),
        ),
    )
    result = run_research(
        [
            FundRecord(
                code="510300",
                name="沪深300ETF",
                category="ETF",
                nav=5.0,
                source="cache:akshare",
            )
        ],
        as_of="2026-06-23",
        provider_health=(health,),
    )

    markdown = render_markdown(result)

    assert "数据源健康状态" in markdown
    assert "akshare" in markdown
    assert "fallback_cache" in markdown
    assert "network down" in markdown
    assert "999999" in markdown


def test_markdown_report_groups_warnings_and_marks_degraded_quality():
    health = ProviderHealth(
        provider="akshare",
        started_at="2026-06-23T00:00:00+00:00",
        finished_at="2026-06-23T00:00:01+00:00",
        duration_ms=1000,
        fallback_used=True,
        fallback_source="cache",
        fallback_reason="network down",
        warnings=(
            ProviderWarning(code="skipped_rows", message="1 bad row", severity="info"),
            ProviderWarning(code="live_fallback", message="using cache", severity="warning"),
            ProviderWarning(code="stale_cache", message="cache expired", severity="critical"),
        ),
    )
    result = run_research(
        [
            FundRecord(
                code="510300",
                name="沪深300ETF",
                category="ETF",
                nav=5.0,
                source="cache:akshare",
                metadata={"stale": True},
            )
        ],
        as_of="2026-06-23",
        provider_health=(health,),
    )

    markdown = render_markdown(result)

    assert "今日数据质量摘要" in markdown
    assert "数据质量等级: degraded" in markdown
    assert markdown.index("### Critical") < markdown.index("### Warning")
    assert markdown.index("### Warning") < markdown.index("### Info")
    assert "stale_cache" in markdown
    assert "live_fallback" in markdown
    assert "skipped_rows" in markdown


def test_markdown_report_includes_data_quality_delta_section():
    result = run_research(
        [FundRecord(code="510300", name="沪深300ETF", category="ETF", nav=5.0)],
        as_of="2026-06-23",
    )
    result = replace(
        result,
        snapshot_delta={
            "previous_as_of": "2026-06-22",
            "score_changes": [],
            "valuation_changes": [],
            "risk_changes": {"added": [], "resolved": []},
            "holding_risk_changes": {},
            "data_quality_grade_delta": {"previous": "normal", "current": "warning"},
            "provider_health_delta": {
                "akshare": {
                    "provider_live_rows_delta": 5,
                    "provider_skipped_rows_delta": 2,
                    "warning_count_delta": 1,
                    "fallback_changed": True,
                }
            },
        },
    )

    markdown = render_markdown(result)

    assert "数据质量变化" in markdown
    assert "normal -> warning" in markdown
    assert "akshare" in markdown
    assert "live rows +5" in markdown


def test_markdown_report_includes_tiantian_optional_enrichment_section():
    result = run_research(
        [FundRecord(code="510300", name="沪深300ETF", category="ETF", nav=5.02)],
        as_of="2026-06-23",
    )
    result = replace(
        result,
        fund_details=(
            FundDetail(
                code="510300",
                name="沪深300ETF",
                fund_company="华泰柏瑞基金",
                fund_manager="张三",
                inception_date="2012-05-04",
                scale=460.5,
                rating="5",
                source="tiantian",
            ),
        ),
        nav_history_summary={
            "510300": {
                "count": 2,
                "start_date": "2026-06-21",
                "end_date": "2026-06-22",
                "latest_unit_nav": 5.02,
                "total_return": 0.2,
                "max_drawdown": 0.0,
                "volatility": 0.1,
                "data_quality_grade": "normal",
            }
        },
    )

    markdown = render_markdown(result)

    assert "基金详情补充数据" in markdown
    assert "华泰柏瑞基金" in markdown
    assert "历史净值摘要" in markdown
    assert "5.0200" in markdown
