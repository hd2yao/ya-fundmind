import json

from fund_agent.cli import main
from fund_agent.contract import validate_contract_file


def _write_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_research_query_cli_writes_default_compact_json(tmp_path, capsys):
    _write_json(
        tmp_path / "market" / "market_intelligence_report.json",
        {
            "schema_version": "1.0",
            "as_of": "2026-07-12",
            "total_funds": 100,
            "records": [{"code": "000001"}],
            "classifications": [{"code": "000001"}],
        },
    )

    exit_code = main(["research-query", "--output-dir", str(tmp_path), "--topic", "market"])

    output = tmp_path / "research_queries" / "research_context.json"
    payload = json.loads(output.read_text(encoding="utf-8"))
    captured = capsys.readouterr()
    assert exit_code == 0
    assert payload["topic"] == "market"
    assert payload["status"] == "ok"
    assert "records" not in payload["data"]["market_intelligence"]
    assert str(output) in captured.out
    assert validate_contract_file(output, "research_context").ok is True


def test_research_query_cli_supports_custom_output_and_partial_status(tmp_path):
    _write_json(
        tmp_path / "fund_agent_report.json",
        {"schema_version": "1.0", "as_of": "2026-07-12", "data_quality_grade": "normal"},
    )
    trace = tmp_path / "traces" / "provider-2026-07-12.json"
    trace.parent.mkdir(parents=True)
    trace.write_text("{invalid", encoding="utf-8")
    output = tmp_path / "custom-context.json"

    exit_code = main(
        [
            "research-query",
            "--output-dir",
            str(tmp_path),
            "--topic",
            "quality",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["status"] == "partial"


def test_research_query_cli_writes_unavailable_context_and_returns_one(tmp_path):
    exit_code = main(["research-query", "--output-dir", str(tmp_path), "--topic", "news"])

    output = tmp_path / "research_queries" / "research_context.json"
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["status"] == "unavailable"
    assert payload["warnings"] == ["no_artifacts_for_topic:news"]


def test_research_query_cli_rejects_invalid_fund_code(tmp_path, capsys):
    exit_code = main(
        [
            "research-query",
            "--output-dir",
            str(tmp_path),
            "--topic",
            "fund",
            "--code",
            "abc",
        ]
    )

    assert exit_code == 2
    assert "Invalid fund code" in capsys.readouterr().out
    assert not (tmp_path / "research_queries" / "research_context.json").exists()


def test_validate_contract_cli_accepts_research_context_file(tmp_path):
    _write_json(
        tmp_path / "ops_status.json",
        {"schema_version": "1.0", "generated_at": "2026-07-12T00:00:00+00:00"},
    )
    assert main(["research-query", "--output-dir", str(tmp_path), "--topic", "quality"]) == 0
    path = tmp_path / "research_queries" / "research_context.json"

    exit_code = main(["validate-contract", "--research-context", str(path)])

    assert exit_code == 0
