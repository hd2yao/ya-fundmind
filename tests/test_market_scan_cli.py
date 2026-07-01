import json

from fund_agent.cli import main


def test_market_scan_cli_writes_market_outputs_without_main_model_changes(tmp_path):
    exit_code = main(
        [
            "market-scan",
            "--provider",
            "fixture",
            "--output-dir",
            str(tmp_path),
            "--as-of",
            "2026-06-23",
            "--min-theme-sample-size",
            "1",
        ]
    )

    report_path = tmp_path / "market" / "market_intelligence_report.json"
    summary_path = tmp_path / "market" / "market_intelligence_summary.md"
    ranking_path = tmp_path / "market" / "market_theme_rankings.json"
    candidates_path = tmp_path / "market" / "market_fund_candidates.json"
    snapshot_path = tmp_path / "market" / "snapshots" / "2026-06-23.json"
    run_report_path = tmp_path / "runs" / "2026-06-23" / "market_intelligence_report.json"
    run_snapshot_path = tmp_path / "runs" / "2026-06-23" / "market_snapshot.json"

    assert exit_code == 0
    assert report_path.exists()
    assert summary_path.exists()
    assert ranking_path.exists()
    assert candidates_path.exists()
    assert snapshot_path.exists()
    assert run_report_path.exists()
    assert run_snapshot_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert payload["not_production_model"] is True
    assert payload["main_score_changed"] is False
    assert payload["main_risk_changed"] is False
    assert payload["total_funds"] > 0
    assert payload["themes"]
    assert snapshot["provider"] == "fixture"
    assert snapshot["run_type"] == "market_scan"
    assert snapshot["theme_count"] > 0
    assert "不接入主评分/主风险" in summary_path.read_text(encoding="utf-8")


def test_market_scan_cli_returns_clear_error_when_no_data(monkeypatch, tmp_path, capsys):
    class EmptyProvider:
        def __init__(self, *args, **kwargs):
            pass

        def fetch_funds(self, *, as_of=None):
            return []

    monkeypatch.setattr("fund_agent.cli.FixtureProvider", EmptyProvider)

    exit_code = main(
        [
            "market-scan",
            "--provider",
            "fixture",
            "--output-dir",
            str(tmp_path),
            "--as-of",
            "2026-06-23",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "No market fund data available" in captured.out
