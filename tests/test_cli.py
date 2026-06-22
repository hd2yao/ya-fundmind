from fund_agent.cli import main


def test_demo_command_writes_markdown_and_html_reports(tmp_path):
    exit_code = main(["demo", "--output-dir", str(tmp_path), "--as-of", "2026-06-22"])

    markdown = tmp_path / "fund_agent_report.md"
    html = tmp_path / "fund_agent_report.html"

    assert exit_code == 0
    assert markdown.exists()
    assert html.exists()
    assert "基金 ETF Agent 日报" in markdown.read_text(encoding="utf-8")
    assert "不构成投资建议" in html.read_text(encoding="utf-8")
