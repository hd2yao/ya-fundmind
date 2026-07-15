from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Protocol

from .models import ResearchAnswer
from .redaction import sanitize_data
from .research_copilot import contains_blocked_research_request


class AnswerRenderer(Protocol):
    def render(self, answer_payload: dict[str, Any]) -> str: ...


def render_research_answer(
    answer: ResearchAnswer,
    *,
    renderer: AnswerRenderer | None = None,
) -> str:
    payload = sanitize_data(json.loads(json.dumps(asdict(answer), ensure_ascii=False)))
    if renderer is not None:
        try:
            rendered = renderer.render(payload)
            if (
                isinstance(rendered, str)
                and rendered.strip()
                and not contains_blocked_research_request(rendered)
            ):
                return rendered
        except Exception:
            pass
    return _render_deterministic_markdown(payload)


def _render_deterministic_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# YA FundMind Research Copilot",
        "",
        f"- 问题：{payload.get('question') or '-'}",
        f"- 状态：{payload.get('answer_status') or 'unknown'}",
        f"- 数据日期：{payload.get('as_of') or '-'}",
        f"- 置信度：{payload.get('confidence') or 'low'}",
        f"- 需要人工复核：{'是' if payload.get('review_required') else '否'}",
        "",
        "## 研究摘要",
        "",
        str(payload.get("summary") or "暂无可用摘要。"),
        "",
        "## 证据化发现",
        "",
    ]
    findings = payload.get("findings") or []
    if findings:
        for finding in findings:
            label = str(finding.get("label") or finding.get("finding_id") or "未命名发现")
            quality = str(finding.get("quality_grade") or "unknown")
            value = json.dumps(finding.get("value"), ensure_ascii=False, sort_keys=True)
            lines.append(f"- **{label}**（{quality}）：`{value}`")
    else:
        lines.append("- 当前没有具备可追溯证据的研究发现。")

    lines.extend(("", "## 证据索引", ""))
    evidence = payload.get("evidence") or []
    if evidence:
        for item in evidence:
            source = str(item.get("source") or "unknown")
            path = str(item.get("path") or "")
            pointer = str(item.get("json_pointer") or "")
            excerpt = str(item.get("excerpt") or "")
            lines.append(f"- `{source}` · `{path}#{pointer}` · {excerpt}")
    else:
        lines.append("- 无。")

    _append_list_section(lines, "数据缺口", payload.get("data_gaps") or [])
    _append_list_section(lines, "Warnings", payload.get("warnings") or [])
    lines.extend(
        (
            "",
            "## 使用边界",
            "",
            "本输出仅用于研究辅助和证据核查，不构成买卖建议，不承诺收益，也不会执行交易。",
            "",
        )
    )
    return "\n".join(lines)


def _append_list_section(lines: list[str], title: str, items: list[Any]) -> None:
    lines.extend(("", f"## {title}", ""))
    if items:
        lines.extend(f"- `{item}`" for item in items)
    else:
        lines.append("- 无。")
