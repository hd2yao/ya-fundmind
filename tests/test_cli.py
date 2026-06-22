from fund_agent.cli import main


def test_demo_command_writes_markdown_and_html_reports(tmp_path):
    exit_code = main(["demo", "--output-dir", str(tmp_path), "--as-of", "2026-06-22"])

    markdown = tmp_path / "fund_agent_report.md"
    html = tmp_path / "fund_agent_report.html"

    assert exit_code == 0
    assert markdown.exists()
    assert html.exists()
    assert "YA FundMind 基金智研系统日报" in markdown.read_text(encoding="utf-8")
    assert "不构成投资建议" in html.read_text(encoding="utf-8")


def test_live_source_failure_returns_nonzero(monkeypatch, tmp_path):
    class FailingProvider:
        def fetch_funds(self):
            raise RuntimeError("network down")

    monkeypatch.setattr("fund_agent.cli.AkshareProvider", lambda: FailingProvider())

    exit_code = main(["screen", "--source", "live", "--output-dir", str(tmp_path)])

    assert exit_code == 2
