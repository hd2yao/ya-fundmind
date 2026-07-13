import json
from pathlib import Path

import pytest

from fund_agent.research_evidence import build_evidence_bundle, resolve_json_pointer
from fund_agent.research_query import ResearchQueryService


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _finding(bundle, claim_type: str):
    return next(item for item in bundle.findings if item["metadata"]["claim_type"] == claim_type)


def _evidence(bundle, evidence_id: str):
    return next(item for item in bundle.evidence if item["evidence_id"] == evidence_id)


def test_market_bundle_links_findings_to_original_json_pointers(tmp_path):
    output_dir = tmp_path / "outputs"
    market_path = output_dir / "market" / "market_intelligence_report.json"
    _write_json(
        market_path,
        {
            "schema_version": "1.0",
            "as_of": "2026-07-12",
            "source": "akshare",
            "total_funds": 21488,
            "total_etfs": 3517,
            "top_themes": [{"theme": "半导体"}],
            "hot_theme_candidates": [{"theme": "人工智能"}],
            "warnings": [],
        },
    )
    _write_json(
        output_dir / "market" / "market_trend_report.json",
        {
            "schema_version": "1.0",
            "latest_as_of": "2026-07-12",
            "source": "akshare",
            "rising_themes": [{"theme": "半导体"}],
            "falling_themes": [],
            "persistent_hot_themes": [{"theme": "人工智能"}],
            "new_hot_themes": [],
            "enough_market_history": True,
        },
    )
    context = ResearchQueryService(output_dir).query("market")

    bundle = build_evidence_bundle(context, output_dir)

    finding = _finding(bundle, "market.total_funds")
    evidence = _evidence(bundle, finding["evidence_ids"][0])
    payload = json.loads(market_path.read_text(encoding="utf-8"))
    assert finding["value"] == 21488
    assert evidence["json_pointer"] == "/total_funds"
    assert resolve_json_pointer(payload, evidence["json_pointer"]) == finding["value"]
    assert bundle.status == "ok"
    assert bundle.quality_grade == "normal"


def test_fund_bundle_uses_matching_list_index_and_reports_missing_fields(tmp_path):
    output_dir = tmp_path / "outputs"
    detail_path = output_dir / "fund_details" / "watchlist_fund_details.json"
    _write_json(
        detail_path,
        {
            "schema_version": "1.0",
            "as_of": "2026-07-12",
            "source": "akshare",
            "fund_details": [
                {"code": "000001", "name": "A"},
                {"code": "000002", "name": "B", "primary_theme": "半导体"},
            ],
        },
    )
    context = ResearchQueryService(output_dir).query("fund", code="000002")

    bundle = build_evidence_bundle(context, output_dir)

    finding = _finding(bundle, "fund.name")
    evidence = _evidence(bundle, finding["evidence_ids"][0])
    assert evidence["json_pointer"] == "/fund_details/1/name"
    assert finding["value"] == "B"
    assert "fund.data_coverage" in bundle.data_gaps
    assert all(item["value"] is not None for item in bundle.findings)


@pytest.mark.parametrize(
    ("topic", "relative_path", "payload", "claim_type", "expected"),
    (
        (
            "portfolio",
            "portfolio/portfolio_report.json",
            {"schema_version": "1.0", "as_of": "2026-07-12", "holding_count": 3, "warnings": []},
            "portfolio.holding_count",
            3,
        ),
        (
            "news",
            "news/news_evidence_report.json",
            {"schema_version": "1.0", "as_of": "2026-07-12", "evidence_count": 2, "warnings": []},
            "news.evidence_count",
            2,
        ),
        (
            "quality",
            "fund_agent_report.json",
            {"schema_version": "1.0", "as_of": "2026-07-12", "data_quality_grade": "normal"},
            "quality.report_grade",
            "normal",
        ),
    ),
)
def test_small_topic_builders_create_cited_findings(
    tmp_path, topic, relative_path, payload, claim_type, expected
):
    output_dir = tmp_path / "outputs"
    _write_json(output_dir / relative_path, payload)
    context = ResearchQueryService(output_dir).query(topic)

    bundle = build_evidence_bundle(context, output_dir)

    finding = _finding(bundle, claim_type)
    assert finding["value"] == expected
    assert finding["evidence_ids"]


def test_history_bundle_cites_latest_snapshot_delta(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(
        output_dir / "snapshots" / "2026-07-11.json",
        {
            "schema_version": "1.0",
            "as_of": "2026-07-11",
            "snapshot_delta": {},
            "provider_warnings": [
                {"code": "all_watchlist_missing", "severity": "critical"}
            ],
        },
    )
    latest = output_dir / "snapshots" / "2026-07-12.json"
    _write_json(
        latest,
        {
            "schema_version": "1.0",
            "as_of": "2026-07-12",
            "snapshot_delta": {"warning_count_delta": 1},
        },
    )
    context = ResearchQueryService(output_dir).query("history")

    bundle = build_evidence_bundle(context, output_dir)

    finding = _finding(bundle, "history.latest_delta")
    evidence = _evidence(bundle, finding["evidence_ids"][0])
    assert evidence["path"] == "snapshots/2026-07-12.json"
    assert evidence["json_pointer"] == "/snapshot_delta"
    assert finding["value"] == {"warning_count_delta": 1}
    assert bundle.quality_grade == "normal"
    assert bundle.review_required is False


def test_bundle_marks_cross_source_conflict_degraded_and_requires_review(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(
        output_dir / "fund_details" / "fund_detail_000001.json",
        {
            "schema_version": "1.0",
            "as_of": "2026-07-12",
            "source": "tiantian",
            "code": "000001",
            "name": "名称B",
        },
    )
    _write_json(
        output_dir / "fund_details" / "watchlist_fund_details.json",
        {
            "schema_version": "1.0",
            "as_of": "2026-07-12",
            "source": "akshare",
            "fund_details": [{"code": "000001", "name": "名称A"}],
        },
    )
    context = ResearchQueryService(output_dir).query("fund", code="000001")

    bundle = build_evidence_bundle(context, output_dir)

    assert bundle.quality_grade == "degraded"
    assert bundle.review_required is True
    assert "evidence_conflict:fund.name" in bundle.warnings


def test_null_source_value_becomes_data_gap_not_finding(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(
        output_dir / "fund_details" / "fund_detail_000001.json",
        {
            "schema_version": "1.0",
            "as_of": "2026-07-12",
            "source": "tiantian",
            "code": "000001",
            "name": None,
        },
    )
    context = ResearchQueryService(output_dir).query("fund", code="000001")

    bundle = build_evidence_bundle(context, output_dir)

    assert "fund.name" in bundle.data_gaps
    assert all(item["metadata"]["claim_type"] != "fund.name" for item in bundle.findings)
