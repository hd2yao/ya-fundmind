import json

from fund_agent.cli import main
from fund_agent.contract import validate_contract_file


def _write_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_research_evidence_cli_writes_valid_bundle(tmp_path, capsys):
    _write_json(
        tmp_path / "market" / "market_intelligence_report.json",
        {
            "schema_version": "1.0",
            "as_of": "2026-07-12",
            "source": "fixture",
            "total_funds": 10,
            "total_etfs": 2,
            "top_themes": [],
            "hot_theme_candidates": [],
        },
    )
    assert main(["research-query", "--output-dir", str(tmp_path), "--topic", "market"]) == 0
    context = tmp_path / "research_queries" / "research_context.json"

    exit_code = main(
        [
            "build-research-evidence",
            "--context",
            str(context),
            "--output-dir",
            str(tmp_path),
        ]
    )

    output = tmp_path / "evidence" / "research_evidence.json"
    payload = json.loads(output.read_text(encoding="utf-8"))
    captured = capsys.readouterr()
    assert exit_code == 0
    assert payload["topic"] == "market"
    assert payload["findings"]
    assert payload["evidence"]
    assert str(output) in captured.out
    assert validate_contract_file(output, "evidence_bundle").ok is True


def test_build_research_evidence_cli_rejects_invalid_context(tmp_path, capsys):
    context = tmp_path / "bad-context.json"
    _write_json(context, {"schema_version": "1.0", "topic": "market"})

    exit_code = main(
        [
            "build-research-evidence",
            "--context",
            str(context),
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 2
    assert "Invalid research context" in capsys.readouterr().out
    assert not (tmp_path / "evidence" / "research_evidence.json").exists()


def test_build_research_evidence_cli_writes_unavailable_bundle_and_returns_one(tmp_path):
    query_exit = main(["research-query", "--output-dir", str(tmp_path), "--topic", "news"])
    assert query_exit == 1

    exit_code = main(
        [
            "build-research-evidence",
            "--context",
            str(tmp_path / "research_queries" / "research_context.json"),
            "--output-dir",
            str(tmp_path),
        ]
    )

    output = tmp_path / "evidence" / "research_evidence.json"
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["status"] == "unavailable"
    assert payload["quality_grade"] == "blocked"


def test_validate_contract_cli_accepts_evidence_bundle(tmp_path):
    _write_json(
        tmp_path / "portfolio" / "portfolio_report.json",
        {"schema_version": "1.0", "as_of": "2026-07-12", "holding_count": 1},
    )
    assert main(["research-query", "--output-dir", str(tmp_path), "--topic", "portfolio"]) == 0
    assert main(
        [
            "build-research-evidence",
            "--context",
            str(tmp_path / "research_queries" / "research_context.json"),
            "--output-dir",
            str(tmp_path),
        ]
    ) == 0

    exit_code = main(
        [
            "validate-contract",
            "--evidence-bundle",
            str(tmp_path / "evidence" / "research_evidence.json"),
        ]
    )

    assert exit_code == 0
