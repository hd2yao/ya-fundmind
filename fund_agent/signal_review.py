from __future__ import annotations

import fnmatch
import json
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import SignalReviewItem


REVIEW_STATUSES = {
    "proposed",
    "needs_data",
    "needs_review",
    "rejected",
    "approved_for_experiment",
    "approved_for_main_candidate",
}
BLOCKING_REASONS = {
    "stale_cache_blocked",
    "missing_required_signal_data",
    "missing_signal_value",
    "missing_tiantian_field",
    "degraded_data_blocked",
    "degraded_window",
    "warning_data_blocked",
    "warning_window",
    "annualized_return_unstable",
}


def load_signal_threshold_candidates(path: Path | str) -> list[dict[str, Any]]:
    config_path = Path(path)
    if not config_path.exists():
        return []
    items: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if not line.startswith(" ") and stripped == "candidates:":
            continue
        if stripped.startswith("- "):
            current = {}
            items.append(current)
            rest = stripped[2:].strip()
            if rest:
                key, value = _split_key_value(rest)
                current[key] = _parse_scalar(value)
            continue
        if current is not None and ":" in stripped:
            key, value = _split_key_value(stripped)
            current[key] = _parse_scalar(value)
            continue
        raise ValueError(f"Unsupported threshold YAML subset in {config_path}: {raw_line}")
    for item in items:
        status = str(item.get("review_status", "proposed"))
        if status not in REVIEW_STATUSES:
            item["review_status"] = "needs_review"
    return items


def review_signal_readiness(
    *,
    signals_payload: dict[str, Any],
    stability_payload: dict[str, Any],
    baseline_payload: dict[str, Any],
    sensitivity_payload: dict[str, Any],
    thresholds: list[dict[str, Any]],
) -> dict[str, Any]:
    review_items = [
        _review_one_threshold(
            threshold,
            signals_payload=signals_payload,
            stability_payload=stability_payload,
            baseline_payload=baseline_payload,
            sensitivity_payload=sensitivity_payload,
        )
        for threshold in thresholds
    ]
    items = [asdict(item) for item in review_items]
    recommended = [item for item in items if item["recommended_status"] == "approved_for_experiment"]
    blocked = [
        item
        for item in items
        if item["recommended_status"] in {"rejected", "needs_review"}
    ]
    needs_more = [item for item in items if item["recommended_status"] == "needs_data"]
    queue = manual_review_queue(items)
    return {
        "review_items": items,
        "recommended_for_experiment": recommended,
        "rejected_or_blocked": blocked,
        "needs_more_data": needs_more,
        "manual_review_required": True,
        "manual_review_queue": queue,
        "summary": {
            "total_review_items": len(items),
            "recommended_for_experiment_count": len(recommended),
            "rejected_or_blocked_count": len(blocked),
            "needs_more_data_count": len(needs_more),
        },
        "warnings": _review_warnings(items),
        "not_production_model": True,
    }


def review_signal_readiness_file(
    *,
    signals_path: Path | str,
    stability_path: Path | str,
    baseline_path: Path | str,
    sensitivity_path: Path | str,
    thresholds_path: Path | str,
    output_path: Path | str,
) -> Path:
    result = review_signal_readiness(
        signals_payload=_load_json(signals_path),
        stability_payload=_load_json(stability_path, optional=True),
        baseline_payload=_load_json(baseline_path, optional=True),
        sensitivity_payload=_load_json(sensitivity_path, optional=True),
        thresholds=load_signal_threshold_candidates(thresholds_path),
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    queue_path = output.parent / "manual_review_queue.json"
    queue_path.write_text(
        json.dumps(result["manual_review_queue"], ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output


def generate_signal_promotion_proposal_file(*, review_path: Path | str, output_path: Path | str) -> Path:
    review = json.loads(Path(review_path).read_text(encoding="utf-8"))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_signal_promotion_proposal(review), encoding="utf-8")
    return output


def render_signal_promotion_proposal(review_payload: dict[str, Any]) -> str:
    items = list(review_payload.get("review_items") or [])
    experiment = [item for item in items if item.get("recommended_status") == "approved_for_experiment"]
    needs_data = [item for item in items if item.get("recommended_status") == "needs_data"]
    rejected = [item for item in items if item.get("recommended_status") in {"rejected", "needs_review"}]
    main_ready = [
        item
        for item in items
        if item.get("recommended_status") == "approved_for_main_candidate"
    ]
    recommend_main = "yes" if main_ready and len(main_ready) == len(items) else "no"
    lines = [
        "# Signal Promotion Proposal",
        "",
        "> 当前没有直接修改主模型；本文件只用于人工审批和后续 PR 评估。",
        "",
        f"- 是否建议进入主模型：{recommend_main}",
        "",
        "## 可以继续实验",
        "",
    ]
    lines.extend(_proposal_items(experiment))
    lines.extend(["", "## 需要更多数据", ""])
    lines.extend(_proposal_items(needs_data))
    lines.extend(["", "## 应拒绝或阻塞", ""])
    lines.extend(_proposal_items(rejected))
    lines.extend(
        [
            "",
            "## 人工审批清单",
            "",
            "- 确认方向假设和阈值候选。",
            "- 确认样本数量、质量等级和 stale cache 处理。",
            "- 确认 warning/degraded/unstable annualized return 不进入主模型。",
            "- 为任何主模型接入单独开 PR 并补主 score / 主 risk 回归测试。",
        ]
    )
    return "\n".join(lines) + "\n"


def manual_review_queue(review_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    queue = []
    for index, item in enumerate(review_items, start=1):
        if not item.get("manual_review_required", True):
            continue
        queue.append(
            {
                "review_id": f"signal-review-{index:04d}",
                "signal_id": item.get("signal_id"),
                "recommended_status": item.get("recommended_status"),
                "required_human_decision": _required_decision(item),
                "reason": "; ".join(item.get("evidence") or []),
                "evidence": item.get("evidence") or [],
                "created_at": now,
            }
        )
    return queue


def _review_one_threshold(
    threshold: dict[str, Any],
    *,
    signals_payload: dict[str, Any],
    stability_payload: dict[str, Any],
    baseline_payload: dict[str, Any],
    sensitivity_payload: dict[str, Any],
) -> SignalReviewItem:
    matching = _matching_signals(threshold, signals_payload)
    observed = len(matching)
    eligible_count = sum(1 for item in matching if item.get("eligible") is True and not item.get("excluded_reason"))
    excluded = [item for item in matching if item.get("excluded_reason") or item.get("eligible") is not True]
    reasons = Counter(str(item.get("excluded_reason") or "display_only") for item in excluded)
    stability = _stability_for_threshold(threshold, stability_payload)
    eligible_rate = _eligible_rate(observed, eligible_count, stability)
    sensitivity_grade = "unstable" if (sensitivity_payload.get("sensitivity_summary") or {}).get("over_sensitive") else "stable"
    data_gate = _data_quality_gate(threshold, reasons, baseline_payload)
    status, evidence = _recommended_status(
        threshold=threshold,
        observed=observed,
        eligible_rate=eligible_rate,
        top_reasons=dict(reasons.most_common(5)),
        stability=stability,
        sensitivity_grade=sensitivity_grade,
        data_gate=data_gate,
    )
    return SignalReviewItem(
        signal_id=str(threshold.get("signal_id_pattern", "*")),
        source=str(threshold.get("source", "unknown")),
        category=str(threshold.get("category", "unknown")),
        direction_hypothesis=str(threshold.get("direction_hypothesis", "unknown")),
        observed_count=observed,
        eligible_count=eligible_count,
        excluded_count=len(excluded),
        eligible_rate=eligible_rate,
        top_exclusion_reasons=dict(reasons.most_common(5)),
        stability_grade=stability["grade"],
        config_sensitivity_grade=sensitivity_grade,
        data_quality_gate=data_gate,
        recommended_status=status,
        manual_review_required=True,
        evidence=tuple(evidence),
        metadata={
            "min_required_points": threshold.get("min_required_points"),
            "required_quality_grade": threshold.get("required_quality_grade"),
            "max_score_adjustment_candidate": threshold.get("max_score_adjustment_candidate"),
            "risk_gate_candidate": threshold.get("risk_gate_candidate", False),
            "review_status": threshold.get("review_status", "proposed"),
        },
    )


def _matching_signals(threshold: dict[str, Any], signals_payload: dict[str, Any]) -> list[dict[str, Any]]:
    pattern = str(threshold.get("signal_id_pattern", "*"))
    category = threshold.get("category")
    source = threshold.get("source")
    items = [
        *(signals_payload.get("eligible_signals") or []),
        *(signals_payload.get("excluded_signals") or []),
        *(signals_payload.get("display_only_signals") or []),
    ]
    return [
        item
        for item in items
        if fnmatch.fnmatch(str(item.get("signal_id", "")), pattern)
        and (category is None or str(item.get("category")) == str(category))
        and (source is None or str(item.get("source", "")).startswith(str(source)))
    ]


def _stability_for_threshold(threshold: dict[str, Any], stability_payload: dict[str, Any]) -> dict[str, Any]:
    by_signal = stability_payload.get("by_signal_id") or {}
    pattern = str(threshold.get("signal_id_pattern", "*"))
    matched = [
        item
        for signal_id, item in by_signal.items()
        if fnmatch.fnmatch(str(signal_id), pattern)
    ]
    if not matched:
        return {"grade": "no_history", "observed_count": 0, "eligible_count": 0, "eligible_rate": None}
    observed = sum(int(item.get("signal_presence_count", 0) or 0) for item in matched)
    eligible = sum(int(item.get("signal_eligible_count", 0) or 0) for item in matched)
    rate = None if observed == 0 else round(eligible / observed, 4)
    grade = "stable" if observed >= 5 and (rate or 0) >= 0.6 else "weak"
    return {"grade": grade, "observed_count": observed, "eligible_count": eligible, "eligible_rate": rate}


def _eligible_rate(observed: int, eligible_count: int, stability: dict[str, Any]) -> float | None:
    if stability.get("eligible_rate") is not None:
        return float(stability["eligible_rate"])
    if observed == 0:
        return None
    return round(eligible_count / observed, 4)


def _data_quality_gate(threshold: dict[str, Any], reasons: Counter[str], baseline_payload: dict[str, Any]) -> str:
    baseline_reasons = (baseline_payload.get("exclusion_diagnostics") or {}).get("excluded_by_reason") or {}
    combined = Counter(reasons)
    combined.update(baseline_reasons)
    if any(reason in combined for reason in BLOCKING_REASONS):
        return "blocked"
    if threshold.get("exclude_if_stale") and combined.get("stale_cache_blocked"):
        return "blocked"
    return "pass"


def _recommended_status(
    *,
    threshold: dict[str, Any],
    observed: int,
    eligible_rate: float | None,
    top_reasons: dict[str, int],
    stability: dict[str, Any],
    sensitivity_grade: str,
    data_gate: str,
) -> tuple[str, list[str]]:
    evidence = [
        f"observed_count={observed}",
        f"eligible_rate={eligible_rate}",
        f"stability_grade={stability['grade']}",
        f"data_quality_gate={data_gate}",
        f"config_sensitivity_grade={sensitivity_grade}",
    ]
    category = str(threshold.get("category", ""))
    configured_status = str(threshold.get("review_status", "proposed"))
    if category == "display_only":
        return "rejected", [*evidence, "display-only signals cannot enter scoring/risk"]
    if configured_status in {"rejected", "needs_data", "needs_review"}:
        return configured_status, [*evidence, f"threshold configured as {configured_status}"]
    if stability["grade"] == "no_history":
        return "needs_data", [*evidence, "missing stability history"]
    if eligible_rate is None or eligible_rate < 0.6:
        return "needs_data", [*evidence, "eligible_rate below threshold"]
    if data_gate == "blocked":
        return "needs_data", [*evidence, f"blocking exclusion reasons={top_reasons}"]
    if sensitivity_grade == "unstable":
        return "needs_review", [*evidence, "config sensitivity is unstable"]
    if configured_status == "approved_for_main_candidate":
        return "approved_for_main_candidate", [*evidence, "threshold manually marked as main candidate"]
    return "approved_for_experiment", evidence


def _review_warnings(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    warnings = []
    if not items:
        warnings.append({"code": "no_review_items", "message": "No threshold candidates were reviewed."})
    if any(item["recommended_status"] == "approved_for_main_candidate" for item in items):
        warnings.append(
            {
                "code": "main_candidate_not_main_model",
                "message": "approved_for_main_candidate does not modify the main model.",
            }
        )
    return warnings


def _proposal_items(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return ["- 无"]
    lines = []
    for item in items:
        evidence = "; ".join(item.get("evidence") or [])
        lines.append(
            "- `{signal}`: status={status}, direction={direction}, min_points={points}, missing_tests={tests}. {evidence}".format(
                signal=item.get("signal_id"),
                status=item.get("recommended_status"),
                direction=item.get("direction_hypothesis"),
                points=(item.get("metadata") or {}).get("min_required_points"),
                tests="main score/risk regression, missing/stale/degraded gates",
                evidence=evidence,
            )
        )
    return lines


def _required_decision(item: dict[str, Any]) -> str:
    status = item.get("recommended_status")
    if status == "approved_for_experiment":
        return "approve continued experiment or request more data"
    if status == "approved_for_main_candidate":
        return "confirm separate main-model PR readiness"
    if status == "rejected":
        return "confirm rejection"
    return "decide whether more data or review is required"


def _load_json(path: Path | str, *, optional: bool = False) -> dict[str, Any]:
    json_path = Path(path)
    if optional and not json_path.exists():
        return {}
    return json.loads(json_path.read_text(encoding="utf-8"))


def _split_key_value(text: str) -> tuple[str, str]:
    key, value = text.split(":", 1)
    return key.strip(), value.strip()


def _parse_scalar(value: str) -> object:
    text = value.strip()
    if not text:
        return ""
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        return text[1:-1]
    lower = text.lower()
    if lower in {"true", "false"}:
        return lower == "true"
    if lower in {"null", "none"}:
        return None
    if text.isdigit():
        return int(text)
    try:
        return float(text)
    except ValueError:
        return text
