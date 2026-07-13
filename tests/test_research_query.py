import json
from pathlib import Path

import pytest

from fund_agent.research_query import ResearchQueryService


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_market_query_returns_compact_context_without_large_record_arrays(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(
        output_dir / "market" / "market_intelligence_report.json",
        {
            "schema_version": "1.0",
            "as_of": "2026-07-12",
            "source": "akshare",
            "total_funds": 20000,
            "total_etfs": 3500,
            "themes": [{"theme": "半导体", "score": 8}],
            "top_themes": [{"theme": "半导体"}],
            "hot_theme_candidates": [{"theme": "人工智能"}],
            "data_quality_summary": {"grade": "warning"},
            "warnings": ["sample_warning"],
            "records": [{"code": "000001"}],
            "classifications": [{"code": "000001", "theme": "半导体"}],
        },
    )
    _write_json(
        output_dir / "market" / "market_trend_report.json",
        {
            "schema_version": "1.0",
            "latest_as_of": "2026-07-12",
            "snapshots_processed": 10,
            "enough_market_history": True,
            "rising_themes": [{"theme": "半导体"}],
            "warnings": [],
        },
    )

    context = ResearchQueryService(output_dir).query("market")

    assert context.status == "ok"
    assert context.as_of == "2026-07-12"
    assert context.data["market_intelligence"]["total_funds"] == 20000
    assert "records" not in context.data["market_intelligence"]
    assert "classifications" not in context.data["market_intelligence"]
    assert context.data["market_trend"]["rising_themes"][0]["theme"] == "半导体"
    assert {item["artifact_type"] for item in context.artifacts} == {"market_intelligence", "market_trend"}


def test_fund_query_selects_requested_code_and_watchlist_summary(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(
        output_dir / "fund_details" / "watchlist_fund_details.json",
        {
            "schema_version": "1.0",
            "as_of": "2026-07-12",
            "coverage_summary": {"average_coverage_ratio": 0.8},
            "fund_details": [
                {"code": "000001", "name": "A"},
                {"code": "000002", "name": "B"},
            ],
        },
    )

    context = ResearchQueryService(output_dir).query("fund", code="000002")

    assert context.status == "ok"
    assert context.code == "000002"
    assert context.data["fund"]["name"] == "B"
    assert context.data["coverage_summary"]["average_coverage_ratio"] == 0.8


def test_fund_query_keeps_all_individual_details_before_selecting_code(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(
        output_dir / "fund_details" / "fund_detail_000001.json",
        {"schema_version": "1.0", "as_of": "2026-07-12", "code": "000001", "name": "A"},
    )
    _write_json(
        output_dir / "fund_details" / "fund_detail_000002.json",
        {"schema_version": "1.0", "as_of": "2026-07-12", "code": "000002", "name": "B"},
    )

    context = ResearchQueryService(output_dir).query("fund", code="000001")

    assert context.status == "ok"
    assert context.data["fund"]["name"] == "A"
    assert len(context.artifacts) == 2


def test_portfolio_and_news_queries_return_small_structured_reports(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(
        output_dir / "portfolio" / "portfolio_report.json",
        {"schema_version": "1.0", "as_of": "2026-07-12", "holding_count": 3, "positions": []},
    )
    _write_json(
        output_dir / "news" / "news_evidence_report.json",
        {"schema_version": "1.0", "as_of": "2026-07-12", "evidence_count": 2, "items": []},
    )
    service = ResearchQueryService(output_dir)

    portfolio = service.query("portfolio")
    news = service.query("news")

    assert portfolio.data["portfolio"]["holding_count"] == 3
    assert news.data["news"]["evidence_count"] == 2


def test_history_query_returns_timeline_without_copying_snapshot_payloads(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(
        output_dir / "snapshots" / "2026-07-11.json",
        {"schema_version": "1.0", "as_of": "2026-07-11", "candidates": {"large": "payload"}},
    )
    _write_json(
        output_dir / "snapshots" / "2026-07-12.json",
        {"schema_version": "1.0", "as_of": "2026-07-12", "snapshot_delta": {"warning_count_delta": 1}},
    )

    context = ResearchQueryService(output_dir).query("history")

    assert [item["as_of"] for item in context.data["timeline"]] == ["2026-07-11", "2026-07-12"]
    assert all("payload" not in item for item in context.data["timeline"])
    assert context.data["latest_delta"] == {"warning_count_delta": 1}


def test_quality_query_handles_bad_artifact_as_partial_and_keeps_good_context(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(
        output_dir / "fund_agent_report.json",
        {
            "schema_version": "1.0",
            "as_of": "2026-07-12",
            "data_quality_grade": "warning",
            "provider_warnings": [{"code": "sample"}],
        },
    )
    trace = output_dir / "traces" / "provider-2026-07-12.json"
    trace.parent.mkdir(parents=True)
    trace.write_text("{invalid", encoding="utf-8")

    context = ResearchQueryService(output_dir).query("quality")

    assert context.status == "partial"
    assert context.data["report"]["data_quality_grade"] == "warning"
    assert any("invalid_json" in warning for warning in context.warnings)


def test_query_does_not_parse_markdown_and_rejects_unknown_topics(tmp_path):
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    (output_dir / "fund_agent_report.md").write_text("# market facts", encoding="utf-8")
    service = ResearchQueryService(output_dir)

    context = service.query("market")

    assert context.status == "unavailable"
    assert context.data == {}
    assert context.warnings == ("no_artifacts_for_topic:market",)
    with pytest.raises(ValueError, match="unsupported research topic"):
        service.query("markdown")
