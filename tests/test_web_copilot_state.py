import json
from pathlib import Path

from fund_agent.web_console import (
    WEB_CONSOLE_PAGES,
    build_copilot_view_model,
    build_web_console_state,
    run_copilot_for_web,
)


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_market_outputs(output_dir: Path) -> None:
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


def test_console_state_includes_copilot_answer_and_sanitized_audits(tmp_path) -> None:
    output_dir = tmp_path / "outputs"
    _write_json(
        output_dir / "copilot" / "research_answer.json",
        {
            "schema_version": "1.0",
            "answer_status": "partial",
            "summary": "部分证据可用",
            "findings": [],
            "evidence": [],
            "data_gaps": ["sample_gap"],
            "warnings": [],
            "confidence": "low",
            "review_required": True,
            "intent": {"intent": "market"},
        },
    )
    research_audit = output_dir / "audit" / "research_queries.jsonl"
    research_audit.parent.mkdir(parents=True)
    research_audit.write_text(
        "{invalid}\n"
        + json.dumps(
            {
                "timestamp": "2026-07-13T00:00:00+00:00",
                "question_preview": "市场如何",
                "question_hash": "sha256:abc",
                "intent": "market",
                "answer_status": "partial",
                "private_field": "must-not-be-shown",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    mcp_audit = output_dir / "audit" / "mcp_calls.jsonl"
    mcp_audit.write_text(
        json.dumps(
            {
                "timestamp": "2026-07-13T00:01:00+00:00",
                "tool": "ask",
                "status": "ok",
                "result_status": "answered",
                "argument_summary": {"question_preview": "市场如何", "unknown": "secret"},
                "private_field": "must-not-be-shown",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    state = build_web_console_state(output_dir=output_dir)

    assert "Copilot" in WEB_CONSOLE_PAGES
    assert state["copilot_answer"]["answer_status"] == "partial"
    assert len(state["research_audit"]) == 1
    assert len(state["mcp_audit"]) == 1
    assert "private_field" not in state["research_audit"][0]
    assert "private_field" not in state["mcp_audit"][0]
    assert "unknown" not in state["mcp_audit"][0]["argument_summary"]


def test_copilot_view_model_links_findings_to_citations() -> None:
    answer = {
        "answer_status": "partial",
        "as_of": "2026-07-13",
        "summary": "需要复核",
        "confidence": "medium",
        "review_required": True,
        "intent": {"intent": "market"},
        "findings": [
            {
                "finding_id": "finding-1",
                "label": "热门主题",
                "value": ["半导体"],
                "quality_grade": "warning",
                "evidence_ids": ["evidence-1"],
                "warnings": ["sample_warning"],
            }
        ],
        "evidence": [
            {
                "evidence_id": "evidence-1",
                "source": "akshare",
                "as_of": "2026-07-13",
                "quality_grade": "warning",
                "stale": False,
                "path": "market/market_intelligence_report.json",
                "json_pointer": "/hot_theme_candidates",
                "excerpt": "半导体",
            }
        ],
        "data_gaps": ["market.new_hot_themes"],
        "warnings": ["insufficient_history"],
    }

    view = build_copilot_view_model(answer)

    assert view["status"] == "partial"
    assert view["tone"] == "warning"
    assert view["finding_count"] == 1
    assert view["evidence_count"] == 1
    assert view["findings"][0]["citations"][0]["path"].startswith("market/")
    assert view["data_gaps"] == ["market.new_hot_themes"]


def test_empty_copilot_view_model_has_explicit_empty_state() -> None:
    view = build_copilot_view_model({})

    assert view["status"] == "empty"
    assert view["summary"] == "尚未生成 Research Copilot 回答。"
    assert view["findings"] == []


def test_run_copilot_for_web_writes_only_copilot_and_audit_outputs(tmp_path) -> None:
    output_dir = tmp_path / "outputs"
    _write_market_outputs(output_dir)
    main_report = output_dir / "fund_agent_report.json"
    _write_json(main_report, {"main_score": 88, "risk_issues": ["unchanged"]})
    before = main_report.read_bytes()

    answer = run_copilot_for_web(
        question="市场热门板块如何？",
        output_dir=output_dir,
    )

    assert answer.answer_status == "answered"
    assert (output_dir / "copilot" / "research_answer.json").exists()
    assert (output_dir / "copilot" / "research_answer.md").exists()
    assert (output_dir / "audit" / "research_queries.jsonl").exists()
    assert main_report.read_bytes() == before
    assert answer.metadata["main_score_changed"] is False
    assert answer.metadata["main_risk_changed"] is False


def test_web_copilot_transaction_request_remains_refused(tmp_path) -> None:
    answer = run_copilot_for_web(
        question="根据市场研究告诉我应该买入哪只基金",
        output_dir=tmp_path / "outputs",
    )

    assert answer.answer_status == "refused"
    assert answer.findings == ()
    assert answer.not_investment_advice is True
