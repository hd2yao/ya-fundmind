import json

from fund_agent.cli import main


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_web_console_cli_dry_run_reports_ready(tmp_path, capsys):
    output_dir = tmp_path / "outputs"
    _write_json(output_dir / "daily_research_summary.json", {"as_of": "2026-06-23", "status": "success"})
    _write_json(output_dir / "weekly_research_summary.json", {"runs_processed": 1})
    _write_json(output_dir / "long_horizon_stability.json", {"enough_history": False, "blockers": []})

    exit_code = main(["web-console", "--output-dir", str(output_dir), "--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Web console ready" in captured.out
    assert "not_production_model=true" in captured.out


def test_web_console_cli_returns_clear_error_when_streamlit_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("fund_agent.cli._streamlit_available", lambda: False)

    exit_code = main(["web-console", "--output-dir", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Streamlit is not installed" in captured.out


def test_web_console_cli_launches_streamlit_with_expected_args(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr("fund_agent.cli._streamlit_available", lambda: True)
    monkeypatch.setattr("fund_agent.cli.subprocess.run", lambda cmd, check=False: calls.append((cmd, check)) or 0)

    exit_code = main(["web-console", "--output-dir", str(tmp_path), "--host", "127.0.0.1", "--port", "8507"])

    assert exit_code == 0
    cmd, check = calls[0]
    assert check is False
    assert cmd[1:4] == ["-m", "streamlit", "run"]
    assert "fund_agent/web_console.py" in cmd[4]
    assert "--server.address" in cmd
    assert "127.0.0.1" in cmd
    assert "--server.port" in cmd
    assert "8507" in cmd
    assert "--output-dir" in cmd
