import json

from fund_agent.cli import main


def test_historical_backfill_cli_writes_backfill_artifacts_without_live_daily_pollution(tmp_path):
    exit_code = main(
        [
            "historical-backfill",
            "--provider",
            "fixture",
            "--start-date",
            "2026-06-21",
            "--end-date",
            "2026-06-23",
            "--output-dir",
            str(tmp_path),
            "--min-theme-sample-size",
            "1",
            "--nav-windows",
            "1m,all",
        ]
    )

    assert exit_code == 0
    report_path = tmp_path / "backfill" / "backfill_report.json"
    summary_path = tmp_path / "backfill" / "backfill_summary.md"
    nav_summary_path = tmp_path / "backfill" / "nav_history_summary.json"
    market_snapshot_path = tmp_path / "market" / "snapshots" / "2026-06-21.json"
    run_metadata_path = tmp_path / "runs" / "2026-06-21" / "run_metadata.json"
    run_market_snapshot_path = tmp_path / "runs" / "2026-06-21" / "market_snapshot.json"

    assert report_path.exists()
    assert summary_path.exists()
    assert nav_summary_path.exists()
    assert market_snapshot_path.exists()
    assert run_metadata_path.exists()
    assert run_market_snapshot_path.exists()
    assert not (tmp_path / "daily_research_summary.json").exists()
    assert not (tmp_path / "runs" / "2026-06-21" / "daily_research_summary.json").exists()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    snapshot = json.loads(market_snapshot_path.read_text(encoding="utf-8"))
    metadata = json.loads(run_metadata_path.read_text(encoding="utf-8"))
    nav_summary = json.loads(nav_summary_path.read_text(encoding="utf-8"))

    assert report["run_type"] == "historical_backfill"
    assert report["provider"] == "fixture"
    assert report["dates_processed"] == ["2026-06-21", "2026-06-22", "2026-06-23"]
    assert report["market_snapshot_count"] == 3
    assert report["nav_summary_count"] > 0
    assert report["not_production_model"] is True
    assert report["main_score_changed"] is False
    assert report["main_risk_changed"] is False
    assert "fixture_synthetic_backfill_not_real_history" in report["warnings"]
    assert snapshot["run_type"] == "historical_backfill"
    assert snapshot["backfill"] is True
    assert metadata["run_type"] == "historical_backfill"
    assert metadata["status"] == "success"
    first_code = next(iter(nav_summary["nav_history_summary"]))
    assert nav_summary["nav_history_summary"][first_code]["run_type"] == "historical_backfill"
    assert nav_summary["nav_history_summary"][first_code]["source"] == "fixture:historical_backfill"
    assert "不是买卖建议" in summary_path.read_text(encoding="utf-8")


def test_market_trend_reads_backfill_snapshots_and_marks_backfill(tmp_path):
    assert (
        main(
            [
                "historical-backfill",
                "--provider",
                "fixture",
                "--start-date",
                "2026-06-21",
                "--end-date",
                "2026-06-23",
                "--output-dir",
                str(tmp_path),
                "--min-theme-sample-size",
                "1",
            ]
        )
        == 0
    )

    exit_code = main(
        [
            "market-trend",
            "--market-dir",
            str(tmp_path / "market"),
            "--output-dir",
            str(tmp_path),
            "--min-snapshots",
            "3",
        ]
    )

    trend = json.loads((tmp_path / "market" / "market_trend_report.json").read_text(encoding="utf-8"))
    summary = (tmp_path / "market" / "market_trend_summary.md").read_text(encoding="utf-8")

    assert exit_code == 0
    assert trend["snapshots_processed"] == 3
    assert trend["backfill_snapshot_count"] == 3
    assert trend["run_type_counts"]["historical_backfill"] == 3
    assert "backfill_snapshot_count: 3" in summary
    assert "买入" not in summary
    assert "卖出" not in summary


def test_fund_detail_reads_backfill_nav_summary_and_displays_marker(tmp_path):
    assert (
        main(
            [
                "historical-backfill",
                "--provider",
                "fixture",
                "--start-date",
                "2026-06-21",
                "--end-date",
                "2026-06-23",
                "--output-dir",
                str(tmp_path),
                "--min-theme-sample-size",
                "1",
                "--nav-windows",
                "1m,all",
            ]
        )
        == 0
    )
    backfill = json.loads((tmp_path / "backfill" / "nav_history_summary.json").read_text(encoding="utf-8"))
    code = next(iter(backfill["nav_history_summary"]))

    exit_code = main(["fund-detail", "--code", code, "--output-dir", str(tmp_path)])

    detail = json.loads((tmp_path / "fund_details" / f"fund_detail_{code}.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "fund_details" / f"fund_detail_{code}.md").read_text(encoding="utf-8")

    assert exit_code == 0
    assert detail["nav_history_summary"]["run_type"] == "historical_backfill"
    assert detail["nav_history_summary"]["backfill"] is True
    assert detail["data_coverage"]["has_nav_history_summary"] is True
    assert "historical_backfill" in markdown
    assert "不构成投资建议" in markdown

