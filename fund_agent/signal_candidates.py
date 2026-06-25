from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import SignalCandidate


DISPLAY_ONLY_FIELDS = ("fund_manager", "fund_company", "inception_date")
REQUIRED_REGRESSION_TESTS = (
    "AKShare/fixture daily reports remain stable.",
    "Missing Tiantian fields never improve score.",
    "Stale Tiantian cache never silently improves score.",
    "Degraded NAV windows are excluded.",
    "Short-sample annualized return is excluded.",
    "Snapshot deltas explain any future score/risk behavior change.",
)


def generate_signal_candidates(report_payload: dict) -> dict:
    candidates: list[SignalCandidate] = []
    candidates.extend(_tiantian_candidates(report_payload))
    candidates.extend(_akshare_candidates(report_payload))
    eligible = [asdict(item) for item in candidates if item.eligible]
    excluded = [asdict(item) for item in candidates if not item.eligible and item.category != "display_only"]
    display_only = [asdict(item) for item in candidates if item.category == "display_only"]
    summary = _summary(eligible, excluded, display_only)
    return {
        "eligible_signals": eligible,
        "excluded_signals": excluded,
        "display_only_signals": display_only,
        "summary": summary,
        "required_regression_tests": list(REQUIRED_REGRESSION_TESTS),
        "warnings": _warnings(report_payload),
    }


def generate_signal_candidates_file(input_path: Path | str, output_path: Path | str) -> Path:
    input_file = Path(input_path)
    payload = json.loads(input_file.read_text(encoding="utf-8"))
    result = generate_signal_candidates(payload)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    _write_matching_snapshot_signal_summary(
        input_file=input_file,
        output_file=output,
        report_payload=payload,
        candidate_payload=result,
    )
    return output


def signal_quality_summary(candidate_payload: dict) -> dict:
    excluded = candidate_payload.get("excluded_signals", [])
    display = candidate_payload.get("display_only_signals", [])
    eligible = candidate_payload.get("eligible_signals", [])
    reasons = Counter(item.get("excluded_reason") for item in excluded if item.get("excluded_reason"))
    return {
        "total_signals": len(eligible) + len(excluded) + len(display),
        "eligible_count": len(eligible),
        "excluded_count": len(excluded),
        "degraded_count": sum(1 for item in excluded if item.get("quality_grade") == "degraded"),
        "warning_count": sum(1 for item in excluded if item.get("quality_grade") == "warning"),
        "display_only_count": len(display),
        "top_exclusion_reasons": dict(reasons.most_common(5)),
    }


def batch_signal_experiment(*, input_dir: Path | str | None = None, snapshot_dir: Path | str | None = None) -> dict:
    directory = Path(snapshot_dir or input_dir or ".")
    files = sorted(directory.glob("*.json"))
    signal_type_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    category_stats: dict[str, Counter[str]] = {}
    source_stats: dict[str, Counter[str]] = {}
    signal_stats: dict[str, Counter[str]] = {}
    trend: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []
    eligible_count = 0
    excluded_count = 0
    display_only_count = 0
    processed = 0
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            warnings.append({"file": path.name, "message": f"invalid JSON: {exc}"})
            continue
        if "eligible_signals" in payload or "excluded_signals" in payload:
            candidate_payload = payload
        elif "signal_quality_summary" in payload:
            summary = payload["signal_quality_summary"]
            file_eligible = int(summary.get("eligible_count", 0))
            file_excluded = int(summary.get("excluded_count", 0))
            file_display = int(summary.get("display_only_count", 0))
            eligible_count += file_eligible
            excluded_count += file_excluded
            display_only_count += file_display
            reason_counts.update(summary.get("top_exclusion_reasons", {}))
            trend.append(
                {
                    "file": path.name,
                    "as_of": payload.get("as_of"),
                    "eligible_count": file_eligible,
                    "excluded_count": file_excluded,
                    "display_only_count": file_display,
                    "data_quality_grade": payload.get("data_quality_grade"),
                }
            )
            processed += 1
            continue
        else:
            if _looks_like_report_payload(payload):
                candidate_payload = generate_signal_candidates(payload)
            else:
                warnings.append({"file": path.name, "message": "missing signal candidate or report fields; skipped"})
                processed += 1
                trend.append(
                    {
                        "file": path.name,
                        "as_of": payload.get("as_of"),
                        "eligible_count": 0,
                        "excluded_count": 0,
                        "display_only_count": 0,
                        "data_quality_grade": payload.get("data_quality_grade"),
                    }
                )
                continue
        processed += 1
        file_eligible = len(candidate_payload.get("eligible_signals", []))
        file_excluded = len(candidate_payload.get("excluded_signals", []))
        file_display = len(candidate_payload.get("display_only_signals", []))
        for item in candidate_payload.get("eligible_signals", []):
            eligible_count += 1
            _record_signal(item, "eligible", signal_type_counts, category_stats, source_stats, signal_stats)
        for item in candidate_payload.get("excluded_signals", []):
            excluded_count += 1
            _record_signal(item, "excluded", signal_type_counts, category_stats, source_stats, signal_stats)
            if item.get("excluded_reason"):
                reason_counts[item["excluded_reason"]] += 1
        for item in candidate_payload.get("display_only_signals", []):
            display_only_count += 1
            _record_signal(item, "display_only", signal_type_counts, category_stats, source_stats, signal_stats)
        trend.append(
            {
                "file": path.name,
                "as_of": candidate_payload.get("as_of") or payload.get("as_of"),
                "eligible_count": file_eligible,
                "excluded_count": file_excluded,
                "display_only_count": file_display,
                "data_quality_grade": payload.get("data_quality_grade"),
            }
        )
    total = eligible_count + excluded_count + display_only_count
    return {
        "files_processed": processed,
        "total_signals": total,
        "eligible_count": eligible_count,
        "excluded_count": excluded_count,
        "display_only_count": display_only_count,
        "eligible_ratio": None if total == 0 else round(eligible_count / total, 4),
        "excluded_ratio": None if total == 0 else round(excluded_count / total, 4),
        "by_category": _stats_dict(category_stats),
        "by_source": _stats_dict(source_stats),
        "by_signal_id": _signal_stats_dict(signal_stats),
        "top_exclusion_reasons": dict(reason_counts.most_common(10)),
        "signal_presence_count": {
            signal_id: int(stats.get("presence", 0))
            for signal_id, stats in sorted(signal_stats.items())
        },
        "signal_eligible_count": {
            signal_id: int(stats.get("eligible", 0))
            for signal_id, stats in sorted(signal_stats.items())
        },
        "signal_eligible_rate": {
            signal_id: _rate(int(stats.get("eligible", 0)), int(stats.get("presence", 0)))
            for signal_id, stats in sorted(signal_stats.items())
        },
        "signal_quality_trend": trend,
        "warnings": warnings,
        "signal_type_counts": dict(signal_type_counts),
        "excluded_reason_distribution": dict(reason_counts),
    }


def write_batch_signal_experiment(result: dict, output_path: Path | str) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return output


def _write_matching_snapshot_signal_summary(
    *,
    input_file: Path,
    output_file: Path,
    report_payload: dict,
    candidate_payload: dict,
) -> None:
    as_of = report_payload.get("as_of")
    if not as_of:
        return
    snapshot_path = input_file.parent / "snapshots" / f"{as_of}.json"
    if not snapshot_path.exists():
        return
    snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    summary = signal_quality_summary(candidate_payload)
    summary["generated_from"] = str(output_file)
    snapshot_payload["signal_quality_summary"] = summary
    snapshot_path.write_text(
        json.dumps(snapshot_payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _looks_like_report_payload(payload: dict) -> bool:
    return any(
        key in payload
        for key in (
            "candidates",
            "valuations",
            "fund_details",
            "nav_history_summary",
            "provider_health",
        )
    )


def _record_signal(
    item: dict,
    state: str,
    signal_type_counts: Counter[str],
    category_stats: dict[str, Counter[str]],
    source_stats: dict[str, Counter[str]],
    signal_stats: dict[str, Counter[str]],
) -> None:
    category = str(item.get("category") or "unknown")
    source = str(item.get("source") or "unknown")
    signal_id = str(item.get("signal_id") or "unknown")
    signal_type_counts[category] += 1
    _counter_for(category_stats, category)[state] += 1
    _counter_for(category_stats, category)["total"] += 1
    _counter_for(source_stats, source)[state] += 1
    _counter_for(source_stats, source)["total"] += 1
    _counter_for(signal_stats, signal_id)["presence"] += 1
    _counter_for(signal_stats, signal_id)[state] += 1


def _counter_for(stats: dict[str, Counter[str]], key: str) -> Counter[str]:
    if key not in stats:
        stats[key] = Counter()
    return stats[key]


def _stats_dict(stats: dict[str, Counter[str]]) -> dict[str, dict[str, Any]]:
    return {
        key: {
            "total_signals": int(counter.get("total", 0)),
            "eligible_count": int(counter.get("eligible", 0)),
            "excluded_count": int(counter.get("excluded", 0)),
            "display_only_count": int(counter.get("display_only", 0)),
            "eligible_ratio": _rate(int(counter.get("eligible", 0)), int(counter.get("total", 0))),
        }
        for key, counter in sorted(stats.items())
    }


def _signal_stats_dict(stats: dict[str, Counter[str]]) -> dict[str, dict[str, Any]]:
    return {
        key: {
            "signal_presence_count": int(counter.get("presence", 0)),
            "signal_eligible_count": int(counter.get("eligible", 0)),
            "signal_eligible_rate": _rate(int(counter.get("eligible", 0)), int(counter.get("presence", 0))),
            "excluded_count": int(counter.get("excluded", 0)),
            "display_only_count": int(counter.get("display_only", 0)),
        }
        for key, counter in sorted(stats.items())
    }


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def _tiantian_candidates(report_payload: dict) -> list[SignalCandidate]:
    items: list[SignalCandidate] = []
    for code, summary in (report_payload.get("nav_history_summary") or {}).items():
        for window, window_summary in (summary.get("windows") or {}).items():
            metadata = window_summary.get("metadata") or {}
            grade = window_summary.get("data_quality_grade", "unknown")
            actual = int(metadata.get("actual_points") or window_summary.get("count") or 0)
            required = int(metadata.get("required_points") or actual or 0)
            if grade == "degraded":
                items.append(_candidate(f"tiantian:{code}:data_quality:{window}", "tiantian", code, "data_quality", grade, "neutral", grade, False, "degraded_window", f"{window} degraded", metadata))
                continue
            if grade == "warning" and not metadata.get("experiment_allow_partial"):
                items.append(_candidate(f"tiantian:{code}:data_quality:{window}", "tiantian", code, "data_quality", grade, "neutral", grade, False, "warning_window", f"{window} warning", metadata))
                continue
            if actual < required:
                items.append(_candidate(f"tiantian:{code}:data_quality:{window}", "tiantian", code, "data_quality", actual, "neutral", "warning", False, "insufficient_sample_points", f"{window} insufficient sample", metadata))
                continue
            field_specs = (
                ("total_return", "return", "positive"),
                ("max_drawdown", "drawdown", "negative"),
                ("volatility", "volatility", "negative"),
            )
            for field, category, direction in field_specs:
                value = window_summary.get(field)
                if value is None:
                    items.append(_candidate(f"tiantian:{code}:{category}:{window}:{field}", "tiantian", code, category, None, direction, "degraded", False, "missing_signal_value", f"{window} missing {field}", metadata))
                else:
                    items.append(_candidate(f"tiantian:{code}:{category}:{window}:{field}", "tiantian", code, category, value, direction, grade, True, None, f"{window} {field}", metadata))
            if metadata.get("annualized_return_unstable"):
                items.append(_candidate(f"tiantian:{code}:return:{window}:annualized_return", "tiantian", code, "return", window_summary.get("annualized_return"), "positive", "warning", False, "annualized_return_unstable", f"{window} annualized_return unstable", metadata))
    for detail in report_payload.get("fund_details") or []:
        code = str(detail.get("code") or "")
        for field in DISPLAY_ONLY_FIELDS:
            if detail.get(field):
                items.append(_candidate(f"tiantian:{code}:display_only:{field}", "tiantian", code, "display_only", detail.get(field), "neutral", "normal", False, "display_only", field, {}))
        for field, category in (("scale", "liquidity"), ("rating", "rating")):
            value = detail.get(field)
            if value is None:
                items.append(_candidate(f"tiantian:{code}:{category}:{field}", "tiantian", code, category, None, "positive", "degraded", False, "missing_tiantian_field", f"missing {field}", {}))
            else:
                items.append(_candidate(f"tiantian:{code}:{category}:{field}", "tiantian", code, category, value, "positive", "normal", True, None, f"fund detail {field}", {"candidate_only": True}))
    return items


def _akshare_candidates(report_payload: dict) -> list[SignalCandidate]:
    items: list[SignalCandidate] = []
    raw_candidates = report_payload.get("candidates") or []
    if isinstance(raw_candidates, dict):
        candidate_items = raw_candidates.values()
    else:
        candidate_items = raw_candidates
    for fund in candidate_items:
        if not hasattr(fund, "get"):
            continue
        code = str(fund.get("code") or "")
        category = fund.get("category")
        if category:
            items.append(_candidate(f"akshare:{code}:display_only:category", "akshare", code, "display_only", category, "neutral", "normal", False, "display_only", "fund category", {}))
        for key in ("scale_billion", "scale"):
            if fund.get(key) is not None:
                items.append(_candidate(f"akshare:{code}:liquidity:{key}", "akshare", code, "liquidity", fund.get(key), "positive", "normal", True, None, key, {}))
        returns = fund.get("returns") or {}
        for period, value in returns.items():
            items.append(_candidate(f"akshare:{code}:return:{period}", "akshare", code, "return", value, "positive", "normal", True, None, f"recent return {period}", {}))
    valuations = report_payload.get("valuations") or {}
    for code, item in valuations.items():
        confidence = item.get("confidence")
        if confidence:
            eligible = str(confidence).lower() == "high"
            items.append(_candidate(f"akshare:{code}:valuation:confidence", "akshare", code, "data_quality", confidence, "positive", "normal", eligible, None if eligible else "low_valuation_confidence", "valuation confidence", {}))
    for health in report_payload.get("provider_health") or []:
        provider = health.get("provider", "provider")
        quality_grade = "warning" if health.get("fallback_used") or health.get("warnings") else "normal"
        items.append(_candidate(f"{provider}:provider:data_quality", provider, "", "data_quality", quality_grade, "positive", quality_grade, quality_grade == "normal", None if quality_grade == "normal" else "provider_data_quality", "provider data quality", {}))
    return items


def _warnings(report_payload: dict) -> list[dict]:
    warnings = []
    if not report_payload.get("fund_details") and not report_payload.get("nav_history_summary"):
        warnings.append({"code": "no_tiantian_enrichment", "message": "No Tiantian enrichment fields found."})
    return warnings


def _summary(eligible: list[dict], excluded: list[dict], display_only: list[dict]) -> dict:
    reasons = Counter(item.get("excluded_reason") for item in excluded if item.get("excluded_reason"))
    degraded = sum(1 for item in excluded if item.get("quality_grade") == "degraded")
    warning = sum(1 for item in excluded if item.get("quality_grade") == "warning")
    return {
        "total_signals": len(eligible) + len(excluded) + len(display_only),
        "eligible_count": len(eligible),
        "excluded_count": len(excluded),
        "degraded_count": degraded,
        "warning_count": warning,
        "display_only_count": len(display_only),
        "top_exclusion_reasons": dict(reasons.most_common(5)),
    }


def _candidate(
    signal_id: str,
    source: str,
    code: str,
    category: str,
    value: Any,
    direction: str,
    quality_grade: str,
    eligible: bool,
    excluded_reason: str | None,
    evidence: str,
    metadata: dict,
) -> SignalCandidate:
    return SignalCandidate(
        signal_id=signal_id,
        source=source,
        code=code,
        category=category,
        value=value,
        direction=direction,
        quality_grade=quality_grade,
        eligible=eligible,
        excluded_reason=excluded_reason,
        evidence=evidence,
        metadata=dict(metadata),
    )
