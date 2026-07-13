from fund_agent.cli import main
from fund_agent.mcp_server import McpDependencyUnavailable


def test_mcp_server_cli_dry_run(monkeypatch, tmp_path, capsys) -> None:
    captured = {}

    def fake_run(output_dir, **kwargs):
        captured["output_dir"] = output_dir
        captured.update(kwargs)
        return {
            "status": "ready",
            "transport": kwargs["transport"],
            "tools": ["status", "catalog", "query", "ask", "evidence"],
        }

    monkeypatch.setattr("fund_agent.cli.run_mcp_server", fake_run)

    exit_code = main(
        [
            "mcp-server",
            "--output-dir",
            str(tmp_path),
            "--timeout-seconds",
            "5",
            "--dry-run",
        ]
    )

    assert exit_code == 0
    assert captured["output_dir"] == tmp_path
    assert captured["timeout_seconds"] == 5.0
    assert captured["transport"] == "stdio"
    assert captured["dry_run"] is True
    assert "status, catalog, query, ask, evidence" in capsys.readouterr().out


def test_mcp_server_cli_reports_missing_dependency(monkeypatch, tmp_path, capsys) -> None:
    def missing(*args, **kwargs):
        raise McpDependencyUnavailable("install optional dependency")

    monkeypatch.setattr("fund_agent.cli.run_mcp_server", missing)

    exit_code = main(["mcp-server", "--output-dir", str(tmp_path), "--dry-run"])

    assert exit_code == 2
    assert "MCP server unavailable" in capsys.readouterr().out
