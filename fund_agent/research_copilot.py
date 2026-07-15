from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .models import EvidenceBundle, ResearchAnswer, ResearchIntent, ResearchPlan
from .redaction import redact_text, sanitize_data
from .research_evidence import build_evidence_bundle
from .research_query import ResearchQueryService


_FUND_CODE_PATTERN = re.compile(r"(?<!\d)(\d{6})(?!\d)")

_BLOCKED_PATTERNS = (
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "下单",
    "仓位建议",
    "交易建议",
    "买什么",
    "买哪",
    "卖什么",
    "卖哪",
    "推荐哪",
    "推荐什么",
    "推荐购买",
    "推荐买",
    "投资建议",
    "操作建议",
    "收益承诺",
    "保证收益",
    "保证年化",
    "保本保收益",
    "申购",
    "赎回",
    "调仓",
    "接入券商",
    "自动交易",
    "交易",
)

_ENGLISH_BLOCKED_PATTERN = re.compile(
    r"\b(?:buy|sell|purchase|trade|subscribe|redeem|rebalance)\b"
    r"|\bguarantee(?:d)?\s+(?:return|yield|profit)\b",
    re.IGNORECASE,
)
_COMPACT_PATTERN = re.compile(r"[\s\u3000_\-·,，。！？!?;；:：]+")

_TOPIC_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("portfolio", ("组合", "持仓", "暴露", "集中度")),
    ("news", ("新闻", "公告", "消息", "舆情", "新闻证据")),
    ("quality", ("数据质量", "数据来源", "来源", "fallback", "stale", "置信度")),
    ("market", ("市场", "板块", "主题", "热点", "行业")),
    ("history", ("历史", "上期", "变化", "趋势", "对比")),
)


def classify_research_intent(question: str) -> ResearchIntent:
    normalized = " ".join(str(question or "").split())
    lowered = normalized.lower()
    code_match = _FUND_CODE_PATTERN.search(normalized)
    code = code_match.group(1) if code_match else None

    if _contains_blocked_request(lowered):
        return ResearchIntent(
            intent="blocked_transaction",
            code=code,
            confidence="high",
            blocked=True,
            reason="transaction_or_recommendation_request",
            normalized_question=normalized,
        )

    if code is not None or any(pattern in lowered for pattern in ("基金", "etf")):
        return ResearchIntent(
            intent="fund",
            code=code,
            confidence="high",
            blocked=False,
            reason=None,
            normalized_question=normalized,
        )

    for intent, patterns in _TOPIC_PATTERNS:
        if any(pattern in lowered for pattern in patterns):
            return ResearchIntent(
                intent=intent,
                code=None,
                confidence="high",
                blocked=False,
                reason=None,
                normalized_question=normalized,
            )

    return ResearchIntent(
        intent="unsupported",
        code=None,
        confidence="low",
        blocked=False,
        reason="unsupported_research_topic",
        normalized_question=normalized,
    )


def _contains_blocked_request(question: str) -> bool:
    request_text = question.replace("交易日", "")
    if _ENGLISH_BLOCKED_PATTERN.search(request_text):
        return True
    compact = _COMPACT_PATTERN.sub("", request_text)
    return any(_COMPACT_PATTERN.sub("", pattern) in compact for pattern in _BLOCKED_PATTERNS)


def contains_blocked_research_request(text: str) -> bool:
    return _contains_blocked_request(str(text or "").lower())


def build_research_plan(question: str) -> ResearchPlan:
    intent = classify_research_intent(question)
    if intent.blocked or intent.intent == "unsupported":
        steps = ("guardrail_response",)
        topic = None
    elif intent.intent == "fund" and intent.code is None:
        steps = ("validate_fund_code", "compose_answer")
        topic = "fund"
    else:
        steps = ("research_query", "build_evidence_bundle", "compose_answer")
        topic = intent.intent
    return ResearchPlan(
        intent=intent.intent,
        topic=topic,
        code=intent.code,
        steps=steps,
        read_only=True,
    )


class ResearchCopilot:
    def __init__(
        self,
        output_dir: Path | str,
        *,
        query_service: Any | None = None,
        evidence_builder: Callable[[Any, Path | str], EvidenceBundle] = build_evidence_bundle,
    ):
        self.output_dir = Path(output_dir)
        self.query_service = query_service or ResearchQueryService(self.output_dir)
        self.evidence_builder = evidence_builder

    def answer(self, question: str) -> ResearchAnswer:
        intent = classify_research_intent(question)
        plan = build_research_plan(question)
        if intent.blocked:
            return self._answer(
                intent,
                plan,
                status="refused",
                summary="该请求涉及交易、仓位或收益承诺，研究助手仅提供只读证据整理。",
                blocked_reason=intent.reason,
                warnings=("read_only_boundary_enforced",),
            )
        if intent.intent == "unsupported":
            return self._answer(
                intent,
                plan,
                status="unsupported",
                summary="当前仅支持市场、基金、组合、新闻、历史和数据质量研究问题。",
                data_gaps=("unsupported_research_topic",),
            )
        if intent.intent == "fund" and intent.code is None:
            return self._answer(
                intent,
                plan,
                status="partial",
                summary="基金研究需要明确的 6 位基金代码，当前未猜测目标基金。",
                data_gaps=("fund_code_required",),
            )

        try:
            context = self.query_service.query(str(plan.topic), code=plan.code)
        except Exception as exc:
            return self._answer(
                intent,
                plan,
                status="unavailable",
                summary="研究数据读取失败，未生成事实结论。",
                data_gaps=(f"research_query_failed:{plan.topic}",),
                warnings=(f"research_query_error:{type(exc).__name__}",),
                review_required=True,
            )

        if context.status == "unavailable":
            return self._answer(
                intent,
                plan,
                status="unavailable",
                as_of=context.as_of,
                summary="当前缺少该主题的可读取 JSON 研究产物。",
                data_gaps=(f"topic_artifacts_unavailable:{plan.topic}",),
                warnings=context.warnings,
                review_required=True,
            )

        try:
            bundle = self.evidence_builder(context, self.output_dir)
        except Exception as exc:
            return self._answer(
                intent,
                plan,
                status="unavailable",
                as_of=context.as_of,
                summary="证据链构建失败，未生成事实结论。",
                data_gaps=(f"evidence_bundle_failed:{plan.topic}",),
                warnings=(*context.warnings, f"evidence_bundle_error:{type(exc).__name__}"),
                review_required=True,
            )

        status = _answer_status(bundle)
        return self._answer(
            intent,
            plan,
            status=status,
            as_of=bundle.as_of,
            summary=_bundle_summary(bundle, status),
            findings=bundle.findings,
            evidence=bundle.evidence,
            data_gaps=bundle.data_gaps,
            warnings=bundle.warnings,
            review_required=bundle.review_required,
            confidence=_confidence_for_quality(bundle.quality_grade),
            extra_metadata={
                "context_status": context.status,
                "evidence_bundle_status": bundle.status,
                "quality_grade": bundle.quality_grade,
            },
        )

    def _answer(
        self,
        intent: ResearchIntent,
        plan: ResearchPlan,
        *,
        status: str,
        summary: str,
        as_of: str | None = None,
        findings: tuple[dict[str, Any], ...] = (),
        evidence: tuple[dict[str, Any], ...] = (),
        data_gaps: tuple[str, ...] = (),
        warnings: tuple[str, ...] = (),
        review_required: bool = False,
        confidence: str = "low",
        blocked_reason: str | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> ResearchAnswer:
        return ResearchAnswer(
            schema_version="1.0",
            generated_at=datetime.now(timezone.utc).isoformat(),
            generator="fund_agent",
            question=redact_text(intent.normalized_question),
            intent=sanitize_data(asdict(intent)),
            answer_status=status,
            as_of=as_of,
            summary=summary,
            findings=findings,
            evidence=evidence,
            data_gaps=data_gaps,
            warnings=tuple(dict.fromkeys(warnings)),
            review_required=review_required,
            confidence=confidence,
            blocked_reason=blocked_reason,
            not_investment_advice=True,
            metadata={
                "read_only": True,
                "plan": asdict(plan),
                "not_production_model": True,
                "main_score_changed": False,
                "main_risk_changed": False,
                **(extra_metadata or {}),
            },
        )


def _answer_status(bundle: EvidenceBundle) -> str:
    if bundle.status == "ok" and bundle.findings:
        return "answered"
    if bundle.findings:
        return "partial"
    return "unavailable"


def _bundle_summary(bundle: EvidenceBundle, status: str) -> str:
    if status == "answered":
        return f"已基于 {len(bundle.evidence)} 条可追溯证据整理 {len(bundle.findings)} 项研究发现。"
    if status == "partial":
        return f"已整理 {len(bundle.findings)} 项研究发现，但存在数据缺口或需人工复核。"
    return "没有足够的可追溯证据生成研究发现。"


def _confidence_for_quality(quality_grade: str) -> str:
    if quality_grade == "normal":
        return "high"
    if quality_grade == "warning":
        return "medium"
    return "low"
