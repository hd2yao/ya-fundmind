import json

from fund_agent.market_intelligence import (
    MarketFundRecord,
    build_market_intelligence_report,
    render_market_intelligence_summary,
    write_market_intelligence_outputs,
)


def test_market_intelligence_report_builds_theme_stats_and_hot_candidates(tmp_path):
    records = [
        MarketFundRecord(
            code=f"51{i:04d}",
            name=f"沪深300ETF{i}",
            fund_type="ETF",
            source="fixture",
            as_of="2026-06-23",
            exchange_traded=True,
            scale=10 + i,
            metadata={"returns": {"1m": 2.0 + i, "3m": 4.0 + i}},
        )
        for i in range(5)
    ]
    records.append(
        MarketFundRecord(
            code="161725",
            name="招商中证白酒指数(LOF)A",
            fund_type="LOF",
            source="fixture",
            as_of="2026-06-23",
            exchange_traded=True,
            metadata={"returns": {"1m": 24.0}},
        )
    )

    report = build_market_intelligence_report(
        records,
        as_of="2026-06-23",
        source="fixture",
        min_theme_sample_size=5,
        top_n=10,
    )

    assert report.not_production_model is True
    assert report.total_funds == 6
    assert report.total_etfs == 5
    assert report.top_themes
    assert report.hot_theme_candidates[0]["theme"] == "沪深300"
    assert all(item["theme"] != "白酒" for item in report.hot_theme_candidates)
    assert any(item["theme"] == "白酒" for item in report.insufficient_sample_themes)
    assert report.data_quality_summary["missing_return_windows"]


def test_market_intelligence_outputs_include_json_markdown_and_run_bundle(tmp_path):
    records = [
        MarketFundRecord(
            code="510300",
            name="沪深300ETF",
            fund_type="ETF",
            source="fixture",
            as_of="2026-06-23",
            exchange_traded=True,
            metadata={"returns": {"1m": 3.2}},
        )
    ]
    report = build_market_intelligence_report(
        records,
        as_of="2026-06-23",
        source="fixture",
        min_theme_sample_size=1,
        top_n=5,
    )

    outputs = write_market_intelligence_outputs(report, tmp_path)
    summary = render_market_intelligence_summary(report)

    assert outputs.report_path.exists()
    assert outputs.summary_path.exists()
    assert outputs.theme_rankings_path.exists()
    assert outputs.fund_candidates_path.exists()
    assert outputs.snapshot_path.exists()
    assert (tmp_path / "runs" / "2026-06-23" / "market_intelligence_report.json").exists()
    assert (tmp_path / "runs" / "2026-06-23" / "market_snapshot.json").exists()
    assert "不是买卖建议" in summary
    payload = json.loads(outputs.report_path.read_text(encoding="utf-8"))
    snapshot = json.loads(outputs.snapshot_path.read_text(encoding="utf-8"))
    assert payload["not_production_model"] is True
    assert payload["themes"]
    assert snapshot["schema_version"] == "1.0"
    assert snapshot["as_of"] == "2026-06-23"
    assert snapshot["provider"] == "fixture"
    assert snapshot["theme_rankings"]
    assert snapshot["not_production_model"] is True
