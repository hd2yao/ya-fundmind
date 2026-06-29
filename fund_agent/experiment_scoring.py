from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, replace
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
    for signal in signals_payload.get("display_only_signals", []) or []:
        global_excluded_signals.append(_signal_view(signal, excluded_reason="display_only"))

    experiment_scores = [_score_result(state, config) for state in score_states.values()]
    applied_signals = [signal for score in experiment_scores for signal in score["applied_signals"]]
    excluded_signals = [
        *[signal for score in experiment_scores for signal in score["excluded_signals"]],
        *global_excluded_signals,
    ]
    diagnostics = exclusion_diagnostics(excluded_signals, config=config)
    return {
        "not_production_model": True,
        "disclaimer": DISCLAIMER,
        "as_of": report_payload.get("as_of"),
        "experiment_scores": experiment_scores,
        "experiment_risk_issues": [asdict(issue) for issue in risk_issues if issue.issue_type],
        "applied_signal_summary": _signal_summary(applied_signals),
        "excluded_signal_summary": _excluded_summary(excluded_signals),
        "exclusion_diagnostics": diagnostics,
        "score_delta_summary": _score_delta_summary(experiment_scores),
        "warnings": _warnings(experiment_scores, applied_signals, diagnostics),
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


def compare_experiment_baseline_file(
    *,
    report_path: Path | str,
    experiment_path: Path | str,
    output_path: Path | str,
) -> Path:
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    experiment = json.loads(Path(experiment_path).read_text(encoding="utf-8"))
    result = compare_experiment_baseline(report_payload=report, experiment_payload=experiment)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return output


def explain_experiment_baseline_file(input_path: Path | str, output_path: Path | str) -> Path:
    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_experiment_baseline_review_markdown(payload), encoding="utf-8")
    return output


def run_experiment_config_sensitivity_file(
    *,
    report_path: Path | str,
    signals_path: Path | str,
    config: ExperimentScoringConfig,
    output_path: Path | str,
) -> Path:
    result = run_experiment_config_sensitivity(
        report_payload=json.loads(Path(report_path).read_text(encoding="utf-8")),
        signals_payload=json.loads(Path(signals_path).read_text(encoding="utf-8")),
        base_config=config,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
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


def compare_experiment_baseline(*, report_payload: dict, experiment_payload: dict) -> dict[str, Any]:
    report_scores = {
        code: item.get("score")
        for code, item in _fund_map(report_payload).items()
    }
    experiment_scores = {
        str(item.get("code")): item
        for item in experiment_payload.get("experiment_scores") or []
        if item.get("code")
    }
    comparison: dict[str, dict[str, Any]] = {}
    warnings: list[dict[str, str]] = []
    funds_with_adjustments: list[dict[str, Any]] = []
    for code, main_score in report_scores.items():
        exp = experiment_scores.get(code)
        if not exp:
            comparison[code] = {
                "main_score": main_score,
                "experiment_score": None,
                "score_delta": None,
                "reason": "experiment_score_missing",
            }
            warnings.append({"code": code, "message": "experiment_score missing for report fund."})
            continue
        delta = exp.get("score_delta")
        comparison[code] = {
            "main_score": main_score,
            "experiment_score": exp.get("experiment_score"),
            "score_delta": delta,
            "applied_signal_count": len(exp.get("applied_signals") or []),
            "excluded_signal_count": len(exp.get("excluded_signals") or []),
        }
        if delta not in (None, 0, 0.0):
            funds_with_adjustments.append(
                {
                    "code": code,
                    "main_score": main_score,
                    "experiment_score": exp.get("experiment_score"),
                    "score_delta": delta,
                }
            )
    risk_by_code = Counter(
        str(item.get("code") or "")
        for item in experiment_payload.get("experiment_risk_issues") or []
    )
    funds_with_risk = [
        {"code": code, "issue_count": count}
        for code, count in sorted(risk_by_code.items())
        if code
    ]
    deltas = [
        float(item.get("score_delta") or 0)
        for item in experiment_scores.values()
        if item.get("score_delta") is not None
    ]
    applied_total = int(experiment_payload.get("applied_signal_summary", {}).get("total", 0) or 0)
    if applied_total == 0:
        warnings.append(
            {
                "code": "zero_applied_signals",
                "message": "applied signals = 0; review exclusion diagnostics before considering main model integration.",
            }
        )
    return {
        "total_funds": len(report_scores),
        "adjusted_count": len(funds_with_adjustments),
        "unchanged_count": len(report_scores) - len(funds_with_adjustments),
        "avg_score_delta": None if not deltas else round(sum(deltas) / len(deltas), 4),
        "max_score_delta": None if not deltas else round(max(abs(delta) for delta in deltas), 4),
        "funds_with_adjustments": funds_with_adjustments,
        "funds_with_experiment_risk_issues": funds_with_risk,
        "main_score_vs_experiment_score": comparison,
        "applied_signal_summary": experiment_payload.get("applied_signal_summary", {}),
        "excluded_signal_summary": experiment_payload.get("excluded_signal_summary", {}),
        "exclusion_diagnostics": experiment_payload.get("exclusion_diagnostics", {}),
        "warnings": warnings,
        "manual_review_required": True,
        "not_production_model": True,
    }


def run_experiment_config_sensitivity(
    *,
    report_payload: dict,
    signals_payload: dict,
    base_config: ExperimentScoringConfig,
) -> dict[str, Any]:
    variants = [
        ("baseline", base_config),
        ("max_score_adjustment=0.25", replace(base_config, max_score_adjustment=0.25)),
        ("max_score_adjustment=0.5", replace(base_config, max_score_adjustment=0.5)),
        ("max_score_adjustment=1.0", replace(base_config, max_score_adjustment=1.0)),
        ("enable_return_signal=false", replace(base_config, enable_return_signal=False)),
        ("enable_drawdown_signal=false", replace(base_config, enable_drawdown_signal=False)),
        ("enable_volatility_signal=false", replace(base_config, enable_volatility_signal=False)),
        ("exclude_warning_windows=false", replace(base_config, exclude_warning_windows=False)),
    ]
    results = []
    for name, config in variants:
        payload = run_experiment_scoring(
            report_payload=report_payload,
            signals_payload=signals_payload,
            config=config,
        )
        summary = experiment_score_summary(payload)
        results.append(
            {
                "variant": name,
                "adjusted_count": summary["adjusted_count"],
                "unchanged_count": summary["unchanged_count"],
                "avg_score_delta": summary["avg_score_delta"],
                "max_score_delta": summary["max_score_delta"],
                "applied_signal_count": summary["applied_signal_count"],
                "excluded_signal_count": summary["excluded_signal_count"],
            }
        )
    adjusted_counts = {item["adjusted_count"] for item in results}
    return {
        "variants": results,
        "sensitivity_summary": {
            "variant_count": len(results),
            "adjusted_count_min": min(adjusted_counts) if adjusted_counts else None,
            "adjusted_count_max": max(adjusted_counts) if adjusted_counts else None,
            "over_sensitive": (max(adjusted_counts) - min(adjusted_counts) > 3) if adjusted_counts else False,
        },
        "warnings": [],
        "not_production_model": True,
    }


def render_experiment_baseline_review_markdown(payload: dict[str, Any]) -> str:
    adjusted = int(payload.get("adjusted_count", 0) or 0)
    lines = [
        "# 实验基线人工审核报告",
        "",
        "> 当前不建议进入主模型；本报告只用于实验校准和人工审核。",
        "",
        "## 当前实验是否产生分数变化",
        "",
        f"- 调整基金数: {adjusted}",
        f"- 未调整基金数: {payload.get('unchanged_count', 0)}",
        f"- 平均 delta: {payload.get('avg_score_delta')}",
        f"- 最大 delta: {payload.get('max_score_delta')}",
        "",
        "## 变化最大的基金",
        "",
    ]
    adjusted_funds = sorted(
        payload.get("funds_with_adjustments") or [],
        key=lambda item: abs(float(item.get("score_delta") or 0)),
        reverse=True,
    )
    if adjusted_funds:
        for item in adjusted_funds[:10]:
            lines.append(f"- {item.get('code')}: delta={item.get('score_delta')}")
    else:
        lines.append("- 无")
    lines.extend(["", "## 哪些信号被应用", ""])
    applied = payload.get("applied_signal_summary") or {}
    applied_ids = applied.get("by_signal_id") or {}
    if applied_ids:
        for signal_id, count in applied_ids.items():
            lines.append(f"- `{signal_id}`: {count}")
    else:
        lines.append("- 无")
    lines.extend(["", "## 哪些信号被排除", ""])
    excluded = payload.get("excluded_signal_summary") or {}
    excluded_ids = excluded.get("by_signal_id") or {}
    if excluded_ids:
        for signal_id, count in excluded_ids.items():
            lines.append(f"- `{signal_id}`: {count}")
    else:
        lines.append("- 无")
    lines.extend(["", "## 排除原因分布", ""])
    diagnostics = payload.get("exclusion_diagnostics") or {}
    by_reason = diagnostics.get("excluded_by_reason") or {}
    if by_reason:
        for reason, count in by_reason.items():
            lines.append(f"- `{reason}`: {count}")
    else:
        lines.append("- 无")
    lines.extend(
        [
            "",
            "## 是否建议进入主模型",
            "",
            "- 不建议进入主模型。",
            "",
            "## 当前不建议进入主模型的原因",
            "",
            "- 当前仍缺少历史稳定性和阈值校准证据。",
            "- 排除信号需要先完成数据质量、stale cache、warning/degraded 处理审查。",
            "- 主 score / 主 risk_issues 需要独立回归基线。",
            "",
            "## 人工审核项",
            "",
            "- 复核 applied signals 的方向假设。",
            "- 复核 excluded signals 的主要原因。",
            "- 对比配置敏感性，确认实验输出不过度敏感。",
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


def exclusion_diagnostics(excluded_signals: list[dict], *, config: ExperimentScoringConfig) -> dict[str, Any]:
    by_reason = Counter(str(item.get("excluded_reason") or "unknown") for item in excluded_signals)
    by_category = Counter(str(item.get("category") or "unknown") for item in excluded_signals)
    by_source = Counter(str(item.get("source") or "unknown") for item in excluded_signals)
    by_quality = Counter(str(item.get("quality_grade") or "unknown") for item in excluded_signals)
    by_config = {
        reason: count
        for reason, count in by_reason.items()
        if reason in {"signal_disabled", "warning_data_blocked", "degraded_data_blocked", "stale_cache_blocked"}
    }
    missing_data_count = sum(
        count
        for reason, count in by_reason.items()
        if reason in {"missing_required_signal_data", "missing_signal_value", "missing_tiantian_field"}
    )
    stale_count = int(by_reason.get("stale_cache_blocked", 0))
    unstable_count = int(by_reason.get("annualized_return_unstable", 0))
    primary_reason = by_reason.most_common(1)[0][0] if by_reason else None
    return {
        "excluded_by_reason": dict(by_reason),
        "excluded_by_category": dict(by_category),
        "excluded_by_source": dict(by_source),
        "excluded_by_quality_grade": dict(by_quality),
        "excluded_by_config": by_config,
        "excluded_by_missing_data": missing_data_count,
        "excluded_by_stale_cache": stale_count,
        "excluded_by_unstable_annualized_return": unstable_count,
        "primary_reason": primary_reason,
        "config": asdict(config),
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
        "warning_data_blocked": "degraded_data_blocked",
        "annualized_return_unstable": "missing_required_signal_data",
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


def _warnings(scores: list[dict], applied_signals: list[dict], diagnostics: dict[str, Any]) -> list[dict[str, str]]:
    warnings = []
    for score in scores:
        if score["base_score"] is None:
            warnings.append({"code": score["code"], "message": "No base score found in report."})
    if not applied_signals:
        primary = diagnostics.get("primary_reason") or "unknown"
        warnings.append(
            {
                "code": "zero_applied_signals",
                "message": f"applied signals = 0; primary exclusion reason: {primary}",
            }
        )
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
