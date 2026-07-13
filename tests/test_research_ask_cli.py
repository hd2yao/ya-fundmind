import json

from fund_agent.cli import main
from fund_agent.contract import validate_contract_file, validate_output_dir


def _write_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_market_outputs(output_dir) -> None:
    _write_json(
        output_dir / "market" / "market_intelligence_report.json",
        {
            "schema_version": "1.0",
            "as_of": "2026-07-13",
            "source": "fixture",
            "total_funds": 100,
            "total_etfs": 20,
            "top_themes": [{"theme": "半导体"}],
            "hot_theme_candidates": [],
            "warnings": [],
        },
    )
    _write_json(
        output_dir / "market" / "market_trend_report.json",
        {
            "schema_version": "1.0",
            "latest_as_of": "2026-07-13",
            "source": "fixture",
            "rising_themes": [{"theme": "半导体"}],
            "falling_themes": [],
            "persistent_hot_themes": [],
            "new_hot_themes": [],
            "enough_market_history": True,
            "warnings": [],
        },
    )


def test_research_ask_writes_json_markdown_and_audit(tmp_path, capsys) -> None:
    _write_market_outputs(tmp_path)

    exit_code = main(
        ["research-ask", "--question", "市场热门板块如何？", "--output-dir", str(tmp_path)]
    )

    json_path = tmp_path / "copilot" / "research_answer.json"
    markdown_path = tmp_path / "copilot" / "research_answer.md"
    audit_path = tmp_path / "audit" / "research_queries.jsonl"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["answer_status"] == "answered"
    assert payload["findings"]
    assert payload["evidence"]
    assert "不构成买卖建议" in markdown_path.read_text(encoding="utf-8")
    assert len(audit_path.read_text(encoding="utf-8").splitlines()) == 1
    assert str(json_path) in capsys.readouterr().out
    assert validate_contract_file(json_path, "research_answer").ok is True
    assert validate_output_dir(tmp_path).ok is True


def test_research_ask_refuses_transaction_but_still_writes_auditable_output(tmp_path) -> None:
    exit_code = main(
        [
            "research-ask",
            "--question",
            "根据市场分析告诉我买入哪只基金",
            "--output-dir",
            str(tmp_path),
        ]
    )

    output = tmp_path / "copilot" / "research_answer.json"
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["answer_status"] == "refused"
    assert payload["findings"] == []
    assert payload["blocked_reason"] == "transaction_or_recommendation_request"
    assert validate_contract_file(output, "research_answer").ok is True


def test_research_ask_supports_custom_output_paths(tmp_path) -> None:
    _write_market_outputs(tmp_path)
    json_path = tmp_path / "custom" / "answer.json"
    markdown_path = tmp_path / "custom" / "answer.md"
    audit_path = tmp_path / "custom" / "audit.jsonl"

    exit_code = main(
        [
            "research-ask",
            "--question",
            "市场热点如何？",
            "--output-dir",
            str(tmp_path),
            "--output",
            str(json_path),
            "--markdown-output",
            str(markdown_path),
            "--audit-output",
            str(audit_path),
        ]
    )

    assert exit_code == 0
    assert json_path.exists()
    assert markdown_path.exists()
    assert audit_path.exists()


def test_validate_contract_cli_accepts_research_answer(tmp_path) -> None:
    _write_market_outputs(tmp_path)
    assert main(
        ["research-ask", "--question", "市场热点如何？", "--output-dir", str(tmp_path)]
    ) == 0

    exit_code = main(
        [
            "validate-contract",
            "--research-answer",
            str(tmp_path / "copilot" / "research_answer.json"),
        ]
    )

    assert exit_code == 0


def test_research_answer_contract_rejects_uncited_finding(tmp_path) -> None:
    path = tmp_path / "invalid-answer.json"
    _write_json(
        path,
        {
            "schema_version": "1.0",
            "generated_at": "2026-07-13T00:00:00+00:00",
            "generator": "fund_agent",
            "question": "市场如何？",
            "intent": {"intent": "market"},
            "answer_status": "answered",
            "as_of": "2026-07-13",
            "summary": "invalid",
            "findings": [{"finding_id": "finding-1", "evidence_ids": []}],
            "evidence": [],
            "data_gaps": [],
            "warnings": [],
            "review_required": False,
            "confidence": "high",
            "blocked_reason": None,
            "not_investment_advice": True,
            "metadata": {},
        },
    )

    validation = validate_contract_file(path, "research_answer")

    assert validation.ok is False
    assert any("at least one evidence" in error for error in validation.errors)
