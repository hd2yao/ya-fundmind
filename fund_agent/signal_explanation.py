from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


DISCLAIMER = "当前不改变主评分/主风险；本报告仅用于候选信号实验和人工研究。"


def explain_signal_candidates(candidate_payload: dict) -> dict[str, Any]:
    eligible = list(candidate_payload.get("eligible_signals") or [])
    excluded = list(candidate_payload.get("excluded_signals") or [])
    display_only = list(candidate_payload.get("display_only_signals") or [])
    summary = candidate_payload.get("summary") or _build_summary(eligible, excluded, display_only)
    reasons = Counter(item.get("excluded_reason") for item in excluded if item.get("excluded_reason"))
    integration_gaps = _integration_gaps(eligible, excluded, display_only)
    json_payload = {
        "summary": summary,
        "top_exclusion_reasons": dict(reasons.most_common(10)),
        "eligible_explanations": [_explain_eligible(item) for item in eligible],
        "excluded_explanations": [_explain_excluded(item) for item in excluded],
        "display_only_explanations": [_explain_display_only(item) for item in display_only],
        "integration_gaps": integration_gaps,
        "disclaimer": DISCLAIMER,
    }
    return {"markdown": _render_markdown(json_payload), "json": json_payload}


def explain_signal_candidates_file(
    input_path: Path | str,
    output_path: Path | str,
    *,
    json_output: Path | str | None = None,
) -> tuple[Path, Path | None]:
    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    result = explain_signal_candidates(payload)
    markdown_path = Path(output_path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(result["markdown"], encoding="utf-8")
    json_path = None
    if json_output is not None:
        json_path = Path(json_output)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(result["json"], ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return markdown_path, json_path


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# 候选信号解释报告",
        "",
        f"> {DISCLAIMER}",
        "",
        "## 信号总览",
        "",
        f"- 总信号数: {summary.get('total_signals', 0)}",
        f"- Eligible: {summary.get('eligible_count', 0)}",
        f"- Excluded: {summary.get('excluded_count', 0)}",
        f"- Display-only: {summary.get('display_only_count', 0)}",
        "",
        "## Eligible Signals",
        "",
    ]
    if payload["eligible_explanations"]:
        for item in payload["eligible_explanations"]:
            lines.append(f"- `{item['signal_id']}`: {item['reason']}")
    else:
        lines.append("- 无")
    lines.extend(["", "## Excluded Signals", ""])
    if payload["excluded_explanations"]:
        for item in payload["excluded_explanations"]:
            lines.append(f"- `{item['signal_id']}`: {item['reason']}")
    else:
        lines.append("- 无")
    lines.extend(["", "## Display-only Signals", ""])
    if payload["display_only_explanations"]:
        for item in payload["display_only_explanations"]:
            lines.append(f"- `{item['signal_id']}`: {item['reason']}")
    else:
        lines.append("- 无")
    lines.extend(["", "## Top Exclusion Reasons", ""])
    if payload["top_exclusion_reasons"]:
        for reason, count in payload["top_exclusion_reasons"].items():
            lines.append(f"- `{reason}`: {count}")
    else:
        lines.append("- 无")
    lines.extend(["", "## 接入评分/风险前缺口", ""])
    for item in payload["integration_gaps"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _explain_eligible(item: dict) -> dict[str, str]:
    evidence = item.get("evidence") or item.get("category") or "candidate evidence"
    return {
        "signal_id": str(item.get("signal_id", "unknown")),
        "reason": f"候选数据质量满足实验门槛，证据: {evidence}。仍需回归测试后才能进入主模型。",
    }


def _explain_excluded(item: dict) -> dict[str, str]:
    reason = item.get("excluded_reason") or "unknown"
    evidence = item.get("evidence") or "--"
    return {
        "signal_id": str(item.get("signal_id", "unknown")),
        "reason": f"排除原因 `{reason}`，证据: {evidence}。",
    }


def _explain_display_only(item: dict) -> dict[str, str]:
    return {
        "signal_id": str(item.get("signal_id", "unknown")),
        "reason": "该字段只提供人工研究上下文，不能直接作为评分或主风险输入。",
    }


def _integration_gaps(eligible: list[dict], excluded: list[dict], display_only: list[dict]) -> list[str]:
    gaps = [
        "需要固定每个 signal_id 的方向假设和缺失字段默认行为。",
        "需要 stale/degraded/warning 数据的回归测试。",
        "需要主评分/主风险变更前后的基线快照对照。",
    ]
    if eligible:
        gaps.append("eligible signals 仍需权重设计和人工确认，不能直接映射到主 score。")
    if excluded:
        gaps.append("excluded signals 需要先解决样本、质量或字段可信度问题。")
    if display_only:
        gaps.append("display-only signals 需要单独可信度模型，否则保持展示用途。")
    return gaps


def _build_summary(eligible: list[dict], excluded: list[dict], display_only: list[dict]) -> dict:
    return {
        "total_signals": len(eligible) + len(excluded) + len(display_only),
        "eligible_count": len(eligible),
        "excluded_count": len(excluded),
        "display_only_count": len(display_only),
    }
