import json

from fund_agent.cli import main


def test_market_trend_cli_writes_trend_outputs_without_advice(tmp_path):
    snapshots = tmp_path / "market" / "snapshots"
    snapshots.mkdir(parents=True)
    snapshot = {
        "schema_version": "1.0",
        "generated_at": "2026-06-23T00:00:00+00:00",
        "as_of": "2026-06-23",
        "source": "fixture",
        "provider": "fixture",
        "run_type": "market_scan",
        "total_funds": 100,
        "total_etfs": 10,
        "theme_count": 1,
        "hot_theme_count": 1,
        "data_quality_grade": "normal",
        "theme_rankings": [{"theme": "半导体", "sample_size": 8, "avg_return_1m": 6.0}],
        "hot_theme_candidates": [{"theme": "半导体", "sample_size": 8, "avg_return_1m": 6.0}],
        "insufficient_sample_themes": [],
        "data_quality_summary": {"grade": "normal"},
        "warnings": [],
        "not_production_model": True,
    }
    (snapshots / "2026-06-23.json").write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "runs" / "2026-06-23").mkdir(parents=True)

    exit_code = main(
        [
            "market-trend",
            "--market-dir",
            str(tmp_path / "market"),
            "--output-dir",
            str(tmp_path),
            "--days",
            "30",
            "--min-snapshots",
            "3",
        ]
    )

    report_path = tmp_path / "market" / "market_trend_report.json"
    summary_path = tmp_path / "market" / "market_trend_summary.md"
    rankings_path = tmp_path / "market" / "theme_trend_rankings.json"
    run_report_path = tmp_path / "runs" / "2026-06-23" / "market_trend_report.json"
    assert exit_code == 0
    assert report_path.exists()
    assert summary_path.exists()
    assert rankings_path.exists()
    assert run_report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["enough_market_history"] is False
    assert payload["snapshots_processed"] == 1
    summary = summary_path.read_text(encoding="utf-8")
    assert "趋势样本不足" in summary
    assert "买入" not in summary
    assert "卖出" not in summary
