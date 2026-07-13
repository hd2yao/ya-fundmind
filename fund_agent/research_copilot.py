from __future__ import annotations

import re

from .models import ResearchIntent


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
    "推荐购买",
    "推荐买",
    "收益承诺",
    "保证收益",
    "接入券商",
    "自动交易",
)

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

    if any(pattern in lowered for pattern in _BLOCKED_PATTERNS):
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
