from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .config import ExperimentScoringFileConfig
from .models import ExperimentRiskIssue, ExperimentScoreResult


ExperimentScoringConfig = ExperimentScoringFileConfig
DISCLAIMER = "Experimental sandbox only. not_production_model=true. This does not change main score or main risk_issues."


def run_experiment_scoring(
    *,
    report_payload: dict,
    signals_payload: dict,
    config: ExperimentScoringConfig,
) -> dict[str, Any]:
    funds = _fund_map(report_payload)
    score_states: dict[str, dict[str, Any]] = {
        code: {
            "code": code,
            "base_score": item.get("score"),
            "applied_signals": [],
            "excluded_signals": [],
            "warnings": [],
            "score_adjustment": 0.0,
        }
        for code, item in funds.items()
    }
    risk_issues: list[ExperimentRiskIssue] = []
    global_excluded_signals: list[dict[str, Any]] = []

    for signal in signals_payload.get("eligible_signals", []) or []:
        code = str(signal.get("code") or "")
        if not code:
            global_excluded_signals.append(_signal_view(signal, excluded_reason="missing_required_signal_data"))
            risk_issues.append(_risk_issue_for_exclusion(signal, "missing_required_signal_data"))
            continue
        if code not in score_states:
            score_states[code] = {
                "code": code,
                "base_score": None,
                "applied_signals": [],
                "excluded_signals": [],
                "warnings": ["Signal code not found in report candidates."],
                "score_adjustment": 0.0,
            }
        exclusion = _exclusion_reason(signal, config)
        if exclusion:
            _exclude_signal(score_states[code], signal, exclusion)
            risk_issues.append(_risk_issue_for_exclusion(signal, exclusion))
            continue
        adjustment = _score_adjustment(signal)
        if adjustment is None:
            _exclude_signal(score_states[code], signal, "missing_required_signal_data")
            risk_issues.append(_risk_issue_for_exclusion(signal, "missing_required_signal_data"))
            continue
        score_states[code]["score_adjustment"] += adjustment
        score_states[code]["applied_signals"].append(_signal_view(signal, adjustment=adjustment))
        risk_issues.extend(_risk_issues_for_applied_signal(signal))

    for signal in signals_payload.get("excluded_signals", []) or []:
        reason = str(signal.get("excluded_reason") or _exclusion_reason(signal, config) or "excluded_candidate")
        code = str(signal.get("code") or "")
        if code and code not in score_states:
            score_states[code] = {
                "code": code,
                "base_score": None,
                "applied_signals": [],
                "excluded_signals": [],
                "warnings": [],
                "score_adjustment": 0.0,
            }
        if code:
            _exclude_signal(score_states[code], signal, reason)
        else:
            global_excluded_signals.append(_signal_view(signal, excluded_reason=reason))
        risk_issues.append(_risk_issue_for_exclusion(signal, reason))

    experiment_scores = [_score_result(state, config) for state in score_states.values()]
    applied_signals = [signal for score in experiment_scores for signal in score["applied_signals"]]
    excluded_signals = [
        *[signal for score in experiment_scores for signal in score["excluded_signals"]],
        *global_excluded_signals,
    ]
    return {
        "not_production_model": True,
        "disclaimer": DISCLAIMER,
        "as_of": report_payload.get("as_of"),
        "experiment_scores": experiment_scores,
        "experiment_risk_issues": [asdict(issue) for issue in risk_issues if issue.issue_type],
        "applied_signal_summary": _signal_summary(applied_signals),
        "excluded_signal_summary": _excluded_summary(excluded_signals),
        "score_delta_summary": _score_delta_summary(experiment_scores),
        "warnings": _warnings(experiment_scores),
        "report_main_risk_issues_count": len(report_payload.get("risk_issues") or []),
        "metadata": {
            "config": asdict(config),
            "main_score_unchanged": True,
            "main_risk_issues_unchanged": True,
        },
    }


def run_experiment_scoring_file(
    *,
    report_path: Path | str,
    signals_path: Path | str,
    config: ExperimentScoringConfig,
    output_path: Path | str,
) -> Path:
    report_file = Path(report_path)
    signals_file = Path(signals_path)
    result = run_experiment_scoring(
        report_payload=json.loads(report_file.read_text(encoding="utf-8")),
        signals_payload=json.loads(signals_file.read_text(encoding="utf-8")),
        config=config,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    _write_matching_snapshot_experiment_summary(report_file, output, result)
    return output


def explain_experiment_scoring_file(input_path: Path | str, output_path: Path | str) -> Path:
    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_experiment_scoring_markdown(payload), encoding="utf-8")
    return output


def render_experiment_scoring_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 实验评分/风险沙箱报告",
        "",
        "> 当前不能进入主模型；本报告不改变主评分、主风险或主报告结论。",
        "",
        "## 实验评分总览",
        "",
        f"- not_production_model: {payload.get('not_production_model')}",
        f"- 基金数量: {len(payload.get('experiment_scores') or [])}",
        f"- 应用信号: {payload.get('applied_signal_summary', {}).get('total', 0)}",
        f"- 排除信号: {payload.get('excluded_signal_summary', {}).get('total', 0)}",
        "",
        "## 分数变化",
        "",
    ]
    for score in payload.get("experiment_scores") or []:
        lines.append(
            "- {code}: base={base}, experiment={experiment}, delta={delta}".format(
                code=score.get("code"),
                base=score.get("base_score"),
                experiment=score.get("experiment_score"),
                delta=score.get("score_delta"),
            )
        )
    lines.extend(["", "## 实验风险", ""])
    issues = payload.get("experiment_risk_issues") or []
    if issues:
        for issue in issues:
            lines.append(f"- `{issue.get('issue_type')}` {issue.get('code')}: {issue.get('reason')}")
    else:
        lines.append("- 无")
    lines.extend(
        [
            "",
            "## 人工审核问题",
            "",
            "- 核对每个 applied signal 的方向假设和阈值。",
            "- 核对 excluded signal 是否由于数据质量、stale cache 或样本不足被排除。",
            "- 在回归基线完成前，实验分数不能进入主 score，实验风险不能进入主 risk_issues。",
        ]
    )
    return "\n".join(lines) + "\n"


def experiment_score_summary(result_payload: dict[str, Any]) -> dict[str, Any]:
    scores = result_payload.get("experiment_scores") or []
    deltas = [float(item.get("score_delta") or 0.0) for item in scores]
    applied = result_payload.get("applied_signal_summary", {}).get("total", 0)
    excluded = result_payload.get("excluded_signal_summary", {}).get("total", 0)
    return {
        "total_funds": len(scores),
        "adjusted_count": sum(1 for delta in deltas if delta != 0),
        "unchanged_count": sum(1 for delta in deltas if delta == 0),
        "avg_score_delta": None if not deltas else round(sum(deltas) / len(deltas), 4),
        "max_score_delta": None if not deltas else round(max(abs(delta) for delta in deltas), 4),
        "applied_signal_count": int(applied),
        "excluded_signal_count": int(excluded),
    }


def _fund_map(report_payload: dict) -> dict[str, dict]:
    raw = report_payload.get("candidates") or []
    if isinstance(raw, dict):
        items = raw.values()
    else:
        items = raw
    return {str(item.get("code")): item for item in items if hasattr(item, "get") and item.get("code")}


def _exclusion_reason(signal: dict, config: ExperimentScoringConfig) -> str | None:
    category = str(signal.get("category") or "")
    metadata = signal.get("metadata") or {}
    grade = str(signal.get("quality_grade") or "normal")
    if category == "display_only":
        return "display_only"
    if not _category_enabled(category, config):
        return "signal_disabled"
    if config.exclude_degraded_windows and grade == "degraded":
        return "degraded_data_blocked"
    if config.exclude_warning_windows and grade == "warning":
        return "warning_data_blocked"
    if metadata.get("annualized_return_unstable"):
        return "annualized_return_unstable"
    if config.exclude_stale_cache and metadata.get("stale"):
        return "stale_cache_blocked"
    confidence = float(metadata.get("signal_confidence", 1.0) or 0.0)
    if confidence < config.min_signal_confidence:
        return "low_confidence_signal"
    return None


def _category_enabled(category: str, config: ExperimentScoringConfig) -> bool:
    return {
        "return": config.enable_return_signal,
        "drawdown": config.enable_drawdown_signal,
        "volatility": config.enable_volatility_signal,
        "liquidity": config.enable_liquidity_signal,
        "rating": config.enable_rating_signal,
        "data_quality": False,
    }.get(category, False)


def _score_adjustment(signal: dict) -> float | None:
    value = signal.get("value")
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    category = str(signal.get("category") or "")
    if category == "return":
        return _clamp(numeric / 10.0, -0.5, 0.5)
    if category == "drawdown":
        return -_clamp(abs(numeric) / 100.0, 0.0, 0.5)
    if category == "volatility":
        return -_clamp(abs(numeric) / 200.0, 0.0, 0.4)
    if category == "liquidity":
        return _clamp(numeric / 1000.0, -0.2, 0.3)
    if category == "rating":
        return _clamp(numeric / 50.0, 0.0, 0.2)
    return None


def _score_result(state: dict[str, Any], config: ExperimentScoringConfig) -> dict[str, Any]:
    raw_delta = float(state["score_adjustment"])
    delta = _clamp(raw_delta, -abs(config.max_score_adjustment), abs(config.max_score_adjustment))
    base_score = state.get("base_score")
    experiment_score = None if base_score is None else round(float(base_score) + delta, 4)
    result = ExperimentScoreResult(
        code=str(state["code"]),
        base_score=None if base_score is None else float(base_score),
        experiment_score=experiment_score,
        score_delta=round(delta, 4),
        applied_signals=tuple(state["applied_signals"]),
        excluded_signals=tuple(state["excluded_signals"]),
        confidence=_confidence(state),
        warnings=tuple(state["warnings"]),
        metadata={"not_production_model": True},
    )
    return asdict(result)


def _confidence(state: dict[str, Any]) -> str:
    if not state["applied_signals"]:
        return "low"
    if state["excluded_signals"]:
        return "medium"
    return "high"


def _exclude_signal(state: dict[str, Any], signal: dict, reason: str) -> None:
    state["excluded_signals"].append(_signal_view(signal, excluded_reason=reason))


def _signal_view(signal: dict, *, adjustment: float | None = None, excluded_reason: str | None = None) -> dict[str, Any]:
    item = {
        "signal_id": signal.get("signal_id"),
        "source": signal.get("source"),
        "code": signal.get("code"),
        "category": signal.get("category"),
        "value": signal.get("value"),
        "quality_grade": signal.get("quality_grade"),
        "metadata": signal.get("metadata") or {},
    }
    if adjustment is not None:
        item["score_adjustment"] = round(adjustment, 4)
    if excluded_reason is not None:
        item["excluded_reason"] = excluded_reason
    return item


def _risk_issues_for_applied_signal(signal: dict) -> list[ExperimentRiskIssue]:
    issues: list[ExperimentRiskIssue] = []
    value = signal.get("value")
    try:
        numeric = abs(float(value))
    except (TypeError, ValueError):
        return issues
    category = signal.get("category")
    if category == "drawdown" and numeric >= 20.0:
        issues.append(_risk_issue(signal, "high_drawdown_candidate", "warning", "Drawdown candidate exceeds sandbox threshold."))
    if category == "volatility" and numeric >= 30.0:
        issues.append(_risk_issue(signal, "high_volatility_candidate", "warning", "Volatility candidate exceeds sandbox threshold."))
    return issues


def _risk_issue_for_exclusion(signal: dict, reason: str) -> ExperimentRiskIssue:
    issue_type = {
        "degraded_data_blocked": "degraded_data_blocked",
        "degraded_window": "degraded_data_blocked",
        "stale_cache_blocked": "stale_cache_blocked",
        "low_confidence_signal": "low_confidence_signal",
        "missing_required_signal_data": "missing_required_signal_data",
        "missing_signal_value": "missing_required_signal_data",
    }.get(reason, "")
    return _risk_issue(signal, issue_type, "warning", reason)


def _risk_issue(signal: dict, issue_type: str, severity: str, reason: str) -> ExperimentRiskIssue:
    return ExperimentRiskIssue(
        code=str(signal.get("code") or ""),
        issue_type=issue_type,
        severity=severity,
        source_signal=str(signal.get("signal_id") or ""),
        reason=reason,
        metadata={"not_main_risk": True},
    )


def _signal_summary(signals: list[dict]) -> dict[str, Any]:
    by_category = Counter(str(item.get("category") or "unknown") for item in signals)
    by_signal_id = Counter(str(item.get("signal_id") or "unknown") for item in signals)
    return {
        "total": len(signals),
        "by_category": dict(by_category),
        "by_signal_id": dict(by_signal_id),
    }


def _excluded_summary(signals: list[dict]) -> dict[str, Any]:
    by_reason = Counter(str(item.get("excluded_reason") or "unknown") for item in signals)
    result = _signal_summary(signals)
    result["by_reason"] = dict(by_reason)
    return result


def _score_delta_summary(scores: list[dict]) -> dict[str, Any]:
    deltas = [float(item.get("score_delta") or 0.0) for item in scores]
    return {
        "adjusted_count": sum(1 for delta in deltas if delta != 0),
        "unchanged_count": sum(1 for delta in deltas if delta == 0),
        "avg_score_delta": None if not deltas else round(sum(deltas) / len(deltas), 4),
        "max_score_delta": None if not deltas else round(max(abs(delta) for delta in deltas), 4),
    }


def _warnings(scores: list[dict]) -> list[dict[str, str]]:
    warnings = []
    for score in scores:
        if score["base_score"] is None:
            warnings.append({"code": score["code"], "message": "No base score found in report."})
    return warnings


def _write_matching_snapshot_experiment_summary(report_file: Path, output_file: Path, result_payload: dict[str, Any]) -> None:
    as_of = result_payload.get("as_of")
    if not as_of:
        return
    snapshot_path = report_file.parent / "snapshots" / f"{as_of}.json"
    if not snapshot_path.exists():
        return
    snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    summary = experiment_score_summary(result_payload)
    summary["generated_from"] = str(output_file)
    snapshot_payload["experiment_score_summary"] = summary
    snapshot_path.write_text(
        json.dumps(snapshot_payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
