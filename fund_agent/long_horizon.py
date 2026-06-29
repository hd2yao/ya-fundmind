from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any


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


def evaluate_long_horizon_stability(
    *,
    runs_dir: Path | str,
    days: int = 30,
    minimum_required_runs: int = 20,
) -> dict[str, Any]:
    run_dirs = _recent_run_dirs(Path(runs_dir), days)
    signal_stats: dict[str, Counter[str]] = defaultdict(Counter)
    reason_counts: Counter[str] = Counter()
    quality_counts: Counter[str] = Counter()
    config_unstable = 0
    for run_dir in run_dirs:
        candidates = _load_json(run_dir / "signal_candidates.json")
        summary = _load_json(run_dir / "daily_research_summary.json")
        quality_counts[str(summary.get("data_quality_grade", "unknown"))] += 1
        if (summary.get("config_sensitivity") or {}).get("over_sensitive"):
            config_unstable += 1
        for item in candidates.get("eligible_signals") or []:
            signal_id = str(item.get("signal_id", "unknown"))
            signal_stats[signal_id]["presence"] += 1
            signal_stats[signal_id]["eligible"] += 1
            signal_stats[signal_id]["category_" + str(item.get("category", "unknown"))] += 1
        for item in candidates.get("excluded_signals") or []:
            signal_id = str(item.get("signal_id", "unknown"))
            signal_stats[signal_id]["presence"] += 1
            signal_stats[signal_id]["excluded"] += 1
            signal_stats[signal_id]["category_" + str(item.get("category", "unknown"))] += 1
            reason = str(item.get("excluded_reason") or "excluded")
            signal_stats[signal_id]["reason_" + reason] += 1
            reason_counts[reason] += 1
        for item in candidates.get("display_only_signals") or []:
            signal_id = str(item.get("signal_id", "unknown"))
            signal_stats[signal_id]["presence"] += 1
            signal_stats[signal_id]["display_only"] += 1
            signal_stats[signal_id]["category_display_only"] += 1
    enough_history = len(run_dirs) >= minimum_required_runs
    suggested: dict[str, str] = {}
    eligible_rate: dict[str, float | None] = {}
    stability_by_id: dict[str, dict[str, Any]] = {}
    blockers: set[str] = set()
    if not enough_history:
        blockers.add("insufficient_history")
    if any(reason in reason_counts for reason in BLOCKING_REASONS):
        blockers.add("recurring_data_quality_blocker")
    if config_unstable:
        blockers.add("config_sensitivity_unstable")
    for signal_id, stats in sorted(signal_stats.items()):
        presence = int(stats.get("presence", 0))
        eligible = int(stats.get("eligible", 0))
        rate = None if presence == 0 else round(eligible / presence, 4)
        eligible_rate[signal_id] = rate
        is_display = int(stats.get("display_only", 0)) > 0 or int(stats.get("category_display_only", 0)) > 0
        has_blocker = any(stats.get("reason_" + reason, 0) for reason in BLOCKING_REASONS)
        if is_display:
            status = "rejected"
        elif not enough_history:
            status = "needs_more_data"
        elif has_blocker:
            status = "blocked"
        elif config_unstable:
            status = "needs_review"
        elif rate is None or rate < 0.6:
            status = "needs_more_data"
        else:
            status = "approved_for_more_experiment"
        suggested[signal_id] = status
        stability_by_id[signal_id] = {
            "presence_count": presence,
            "eligible_count": eligible,
            "excluded_count": int(stats.get("excluded", 0)),
            "display_only_count": int(stats.get("display_only", 0)),
            "eligible_rate": rate,
        }
    return {
        "runs_processed": len(run_dirs),
        "minimum_required_runs": minimum_required_runs,
        "enough_history": enough_history,
        "signal_stability_by_id": stability_by_id,
        "eligible_rate_by_signal": eligible_rate,
        "exclusion_reason_consistency": dict(reason_counts.most_common(10)),
        "data_quality_consistency": dict(quality_counts),
        "config_sensitivity_consistency": {
            "unstable_count": config_unstable,
            "stable_count": max(len(run_dirs) - config_unstable, 0),
        },
        "suggested_review_status": suggested,
        "blockers": sorted(blockers),
        "not_production_model": True,
    }


def write_long_horizon_stability(result: dict[str, Any], output_path: Path | str) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return output


def _recent_run_dirs(runs_dir: Path, days: int) -> list[Path]:
    if not runs_dir.exists():
        return []
    candidates = sorted(path for path in runs_dir.iterdir() if path.is_dir() and _parse_date(path.name))
    if not candidates:
        return []
    end = _parse_date(candidates[-1].name) or date.today()
    start = end - timedelta(days=max(days, 1) - 1)
    return [path for path in candidates if start <= (_parse_date(path.name) or start - timedelta(days=1)) <= end]


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
