import json
from dataclasses import asdict
from pathlib import Path

from fund_agent.models import ResearchContext
from fund_agent.research_copilot import ResearchCopilot, build_research_plan
from fund_agent.research_evidence import build_evidence_bundle


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_plan_is_read_only_and_uses_existing_query_and_evidence_layers() -> None:
    plan = build_research_plan("最近市场热门板块如何？")

    assert plan.topic == "market"
    assert plan.read_only is True
    assert plan.steps == ("research_query", "build_evidence_bundle", "compose_answer")


def test_answer_preserves_bundle_findings_and_evidence(tmp_path) -> None:
    output_dir = tmp_path / "outputs"
    _write_json(
        output_dir / "market" / "market_intelligence_report.json",
        {
            "schema_version": "1.0",
            "as_of": "2026-07-13",
            "source": "akshare",
            "total_funds": 120,
            "total_etfs": 30,
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
            "source": "akshare",
            "rising_themes": [{"theme": "半导体"}],
            "falling_themes": [],
            "persistent_hot_themes": [],
            "new_hot_themes": [],
            "enough_market_history": True,
            "warnings": [],
        },
    )
    copilot = ResearchCopilot(output_dir)

    answer = copilot.answer("最近市场热门板块如何？")
    context = copilot.query_service.query("market")
    bundle = build_evidence_bundle(context, output_dir)

    assert answer.answer_status == "answered"
    assert answer.findings == bundle.findings
    assert answer.evidence == bundle.evidence
    assert answer.as_of == "2026-07-13"
    assert answer.metadata["read_only"] is True
    assert answer.metadata["main_score_changed"] is False
    assert answer.metadata["main_risk_changed"] is False


def test_fund_question_without_code_returns_partial_without_guessing(tmp_path) -> None:
    answer = ResearchCopilot(tmp_path / "outputs").answer("分析一下这只基金")

    assert answer.answer_status == "partial"
    assert answer.findings == ()
    assert answer.evidence == ()
    assert answer.data_gaps == ("fund_code_required",)


def test_missing_topic_artifacts_returns_unavailable(tmp_path) -> None:
    answer = ResearchCopilot(tmp_path / "outputs").answer("组合集中度如何？")

    assert answer.answer_status == "unavailable"
    assert answer.findings == ()
    assert "no_artifacts_for_topic:portfolio" in answer.warnings


class _FailIfQueried:
    def query(self, topic: str, *, code: str | None = None) -> ResearchContext:
        raise AssertionError("blocked and unsupported questions must not query artifacts")


def test_blocked_request_is_refused_before_data_access(tmp_path) -> None:
    copilot = ResearchCopilot(tmp_path / "outputs", query_service=_FailIfQueried())

    answer = copilot.answer("根据研究结果告诉我买入哪一只基金")

    assert answer.answer_status == "refused"
    assert answer.blocked_reason == "transaction_or_recommendation_request"
    assert answer.not_investment_advice is True
    assert answer.findings == ()


def test_unsupported_request_does_not_access_data(tmp_path) -> None:
    copilot = ResearchCopilot(tmp_path / "outputs", query_service=_FailIfQueried())

    answer = copilot.answer("帮我写一个旅行计划")

    assert answer.answer_status == "unsupported"
    assert answer.findings == ()
    assert answer.data_gaps == ("unsupported_research_topic",)


def test_all_six_topics_can_be_planned_without_network() -> None:
    questions = (
        "市场热点如何？",
        "基金 021511 的详情如何？",
        "组合暴露如何？",
        "新闻证据有哪些？",
        "历史趋势如何变化？",
        "数据质量怎么样？",
    )

    plans = tuple(build_research_plan(question) for question in questions)

    assert {plan.topic for plan in plans} == {
        "market",
        "fund",
        "portfolio",
        "news",
        "history",
        "quality",
    }
    assert all(asdict(plan)["read_only"] is True for plan in plans)
