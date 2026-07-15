import json

from fund_agent.audit import append_research_audit
from fund_agent.models import ResearchAnswer


def _answer(question: str) -> ResearchAnswer:
    return ResearchAnswer(
        schema_version="1.0",
        generated_at="2026-07-13T12:00:00+00:00",
        generator="fund_agent",
        question=question,
        intent={"intent": "quality", "code": None, "blocked": False},
        answer_status="answered",
        as_of="2026-07-13",
        summary="数据质量证据已整理。",
        findings=({"finding_id": "finding-1"},),
        evidence=({"evidence_id": "evidence-1"},),
        data_gaps=(),
        warnings=(),
        review_required=False,
        confidence="high",
    )


def test_audit_is_append_only_and_redacts_secret_values(tmp_path) -> None:
    audit_path = tmp_path / "audit" / "research_queries.jsonl"
    question = "数据质量如何？ api_key=secret-123 password: hunter2 Bearer token-value"

    append_research_audit(
        _answer(question),
        audit_path,
        output_path=tmp_path / "copilot" / "research_answer.json",
    )
    append_research_audit(_answer("再查一次数据来源"), audit_path)

    records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 2
    assert records[0]["question_hash"].startswith("sha256:")
    assert records[0]["schema_version"] == "1.0"
    assert records[0]["generated_at"]
    assert records[0]["generator"] == "fund_agent"
    assert "secret-123" not in records[0]["question_preview"]
    assert "hunter2" not in records[0]["question_preview"]
    assert "token-value" not in records[0]["question_preview"]
    assert "[REDACTED]" in records[0]["question_preview"]
    assert records[0]["finding_count"] == 1
    assert records[0]["evidence_count"] == 1
    assert records[0]["output_path"].endswith("research_answer.json")
    assert "question" not in records[0]
