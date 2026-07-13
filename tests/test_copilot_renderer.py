from fund_agent.copilot_renderer import render_research_answer
from fund_agent.models import ResearchAnswer


def _answer() -> ResearchAnswer:
    return ResearchAnswer(
        schema_version="1.0",
        generated_at="2026-07-13T12:00:00+00:00",
        generator="fund_agent",
        question="市场情况如何？",
        intent={"intent": "market", "code": None, "blocked": False},
        answer_status="partial",
        as_of="2026-07-13",
        summary="已整理 1 项研究发现，但存在数据缺口或需人工复核。",
        findings=(
            {
                "finding_id": "finding-1",
                "label": "热门主题",
                "value": [{"theme": "半导体"}],
                "quality_grade": "warning",
                "evidence_ids": ["evidence-1"],
            },
        ),
        evidence=(
            {
                "evidence_id": "evidence-1",
                "source": "akshare",
                "path": "market/market_intelligence_report.json",
                "json_pointer": "/hot_theme_candidates",
                "excerpt": "半导体",
            },
        ),
        data_gaps=("market.new_hot_themes",),
        warnings=("insufficient_history",),
        review_required=True,
        confidence="medium",
        metadata={"read_only": True},
    )


def test_deterministic_renderer_includes_findings_evidence_and_boundary() -> None:
    markdown = render_research_answer(_answer())

    assert "# YA FundMind Research Copilot" in markdown
    assert "热门主题" in markdown
    assert "market/market_intelligence_report.json#/hot_theme_candidates" in markdown
    assert "market.new_hot_themes" in markdown
    assert "insufficient_history" in markdown
    assert "不构成买卖建议" in markdown


class _MutatingRenderer:
    def render(self, answer_payload):
        answer_payload["summary"] = "被篡改"
        answer_payload["findings"].clear()
        return "可选渲染文本"


def test_optional_renderer_receives_copy_and_cannot_change_answer() -> None:
    answer = _answer()

    rendered = render_research_answer(answer, renderer=_MutatingRenderer())

    assert rendered == "可选渲染文本"
    assert answer.summary != "被篡改"
    assert len(answer.findings) == 1


class _FailingRenderer:
    def render(self, answer_payload):
        raise RuntimeError("renderer unavailable")


def test_optional_renderer_failure_falls_back_to_deterministic_markdown() -> None:
    markdown = render_research_answer(_answer(), renderer=_FailingRenderer())

    assert "# YA FundMind Research Copilot" in markdown
    assert "热门主题" in markdown
