from __future__ import annotations

import json
import shutil
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class ResearchStepResult:
    step_name: str
    status: str
    started_at: str
    finished_at: str
    duration_ms: int
    output_paths: tuple[str, ...] = ()
    error_message: str | None = None

    @classmethod
    def success(cls, step_name: str, *, output_paths: tuple[Path | str, ...] = ()) -> "ResearchStepResult":
        now = _utc_now()
        return cls(
            step_name=step_name,
            status="success",
            started_at=now,
            finished_at=now,
            duration_ms=0,
            output_paths=tuple(str(path) for path in output_paths),
        )

    @classmethod
    def failed(
        cls,
        step_name: str,
        *,
        error_message: str,
        output_paths: tuple[Path | str, ...] = (),
    ) -> "ResearchStepResult":
        now = _utc_now()
        return cls(
            step_name=step_name,
            status="failed",
            started_at=now,
            finished_at=now,
            duration_ms=0,
            output_paths=tuple(str(path) for path in output_paths),
            error_message=error_message,
        )


@dataclass(frozen=True)
class RunBundleResult:
    run_dir: Path
    copied_artifacts: tuple[str, ...]
    missing_artifacts: tuple[str, ...]


def execute_research_step(
    step_name: str,
    action: Callable[[], int | None],
    *,
    output_paths: tuple[Path | str, ...] = (),
) -> ResearchStepResult:
    started = _utc_now()
    start_time = datetime.now(timezone.utc)
    try:
        exit_code = action()
        if exit_code not in (None, 0):
            raise RuntimeError(f"exit_code={exit_code}")
        status = "success"
        error_message = None
    except Exception as exc:  # intentional: step runner must record failures and continue when configured.
        status = "failed"
        error_message = str(exc)
    finished_dt = datetime.now(timezone.utc)
    return ResearchStepResult(
        step_name=step_name,
        status=status,
        started_at=started,
        finished_at=finished_dt.isoformat(),
        duration_ms=int((finished_dt - start_time).total_seconds() * 1000),
        output_paths=tuple(str(path) for path in output_paths),
        error_message=error_message,
    )


def write_run_bundle(
    *,
    output_dir: Path | str,
    as_of: str,
    run_dir: Path | str | None = None,
    include_markdown_reports: bool = True,
    include_json_reports: bool = True,
) -> RunBundleResult:
    root = Path(output_dir)
    run_dir = Path(run_dir) if run_dir is not None else root / "runs" / as_of
    run_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[tuple[Path, Path, str]] = []
    if include_markdown_reports:
        artifacts.extend(
            [
                (root / "fund_agent_report.md", run_dir / "fund_agent_report.md", "fund_agent_report.md"),
                (root / "fund_agent_report.html", run_dir / "fund_agent_report.html", "fund_agent_report.html"),
                (root / "experiment_scoring_explained.md", run_dir / "experiment_scoring_explained.md", "experiment_scoring_explained.md"),
                (root / "signal_promotion_proposal.md", run_dir / "signal_promotion_proposal.md", "signal_promotion_proposal.md"),
                (root / "daily_research_summary.md", run_dir / "daily_research_summary.md", "daily_research_summary.md"),
            ]
        )
    if include_json_reports:
        artifacts.extend(
            [
                (root / "fund_agent_report.json", run_dir / "fund_agent_report.json", "fund_agent_report.json"),
                (root / "signal_candidates.json", run_dir / "signal_candidates.json", "signal_candidates.json"),
                (root / "experiment_scoring_report.json", run_dir / "experiment_scoring_report.json", "experiment_scoring_report.json"),
                (root / "experiment_baseline_comparison.json", run_dir / "experiment_baseline_comparison.json", "experiment_baseline_comparison.json"),
                (root / "experiment_config_sensitivity.json", run_dir / "experiment_config_sensitivity.json", "experiment_config_sensitivity.json"),
                (root / "signal_readiness_review.json", run_dir / "signal_readiness_review.json", "signal_readiness_review.json"),
                (root / "manual_review_queue.json", run_dir / "manual_review_queue.json", "manual_review_queue.json"),
                (root / "daily_research_summary.json", run_dir / "daily_research_summary.json", "daily_research_summary.json"),
                (root / "snapshots" / f"{as_of}.json", run_dir / "snapshot.json", "snapshot.json"),
                (root / "traces" / f"provider-{as_of}.json", run_dir / "provider_trace.json", "provider_trace.json"),
            ]
        )
    copied: list[str] = []
    missing: list[str] = []
    for source, target, label in artifacts:
        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(label)
        else:
            missing.append(label)
    return RunBundleResult(
        run_dir=run_dir,
        copied_artifacts=tuple(copied),
        missing_artifacts=tuple(missing),
    )


def write_daily_research_summary(
    *,
    output_dir: Path | str,
    as_of: str,
    steps: tuple[ResearchStepResult, ...],
    started_at: str,
    finished_at: str,
    duration_ms: int,
    status: str,
    missing_artifacts: list[str] | tuple[str, ...],
) -> tuple[Path, Path]:
    root = Path(output_dir)
    payload = build_daily_research_summary(
        output_dir=root,
        as_of=as_of,
        steps=steps,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        status=status,
        missing_artifacts=tuple(missing_artifacts),
    )
    json_path = root / "daily_research_summary.json"
    markdown_path = root / "daily_research_summary.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_daily_research_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def build_daily_research_summary(
    *,
    output_dir: Path,
    as_of: str,
    steps: tuple[ResearchStepResult, ...],
    started_at: str,
    finished_at: str,
    duration_ms: int,
    status: str,
    missing_artifacts: tuple[str, ...],
) -> dict[str, Any]:
    report = _load_json(output_dir / "fund_agent_report.json")
    signals = _load_json(output_dir / "signal_candidates.json")
    experiment = _load_json(output_dir / "experiment_scoring_report.json")
    baseline = _load_json(output_dir / "experiment_baseline_comparison.json")
    sensitivity = _load_json(output_dir / "experiment_config_sensitivity.json")
    readiness = _load_json(output_dir / "signal_readiness_review.json")
    manual_queue = _load_json(output_dir / "manual_review_queue.json", default=[])
    proposal = _read_text(output_dir / "signal_promotion_proposal.md")
    provider_warnings = report.get("provider_warnings") or []
    exclusions = (experiment.get("exclusion_diagnostics") or {}).get("excluded_by_reason") or {}
    return {
        "as_of": as_of,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": duration_ms,
        "status": status,
        "steps": [asdict(step) for step in steps],
        "data_source": {
            "provider_health": report.get("provider_health") or [],
            "provider_warning_count": len(provider_warnings),
        },
        "data_quality_grade": report.get("data_quality_grade", "unknown"),
        "provider_warnings": _warning_summary(provider_warnings),
        "signal_candidates": signals.get("summary", {}),
        "experiment_scoring": {
            "applied_signal_count": (experiment.get("applied_signal_summary") or {}).get("total", 0),
            "excluded_signal_count": (experiment.get("excluded_signal_summary") or {}).get("total", 0),
            "top_exclusion_reasons": _top_dict(exclusions),
            "score_delta_summary": experiment.get("score_delta_summary") or {},
        },
        "baseline_comparison": {
            "adjusted_count": baseline.get("adjusted_count", 0),
            "unchanged_count": baseline.get("unchanged_count", 0),
            "avg_score_delta": baseline.get("avg_score_delta"),
            "max_score_delta": baseline.get("max_score_delta"),
        },
        "config_sensitivity": sensitivity.get("sensitivity_summary", {}),
        "readiness_review": readiness.get("summary", {}),
        "manual_review_queue": _manual_queue_summary(manual_queue),
        "recommend_main_model": _recommendation_from_proposal(proposal),
        "main_score_changed": False,
        "main_risk_changed": False,
        "missing_artifacts": list(missing_artifacts),
        "not_production_model": True,
    }


def render_daily_research_markdown(payload: dict[str, Any]) -> str:
    signal_summary = payload.get("signal_candidates") or {}
    experiment = payload.get("experiment_scoring") or {}
    readiness = payload.get("readiness_review") or {}
    manual_queue = payload.get("manual_review_queue") or {}
    lines = [
        "# Daily Research Summary",
        "",
        f"- 日期: {payload.get('as_of')}",
        f"- 状态: {payload.get('status')}",
        f"- 数据质量: {payload.get('data_quality_grade')}",
        f"- 是否建议进入主模型: {payload.get('recommend_main_model', 'no')}",
        "- 没有修改主评分/主风险；没有改变主报告结论。",
        "",
        "## Step 状态",
        "",
    ]
    for step in payload.get("steps") or []:
        lines.append(f"- {step.get('step_name')}: {step.get('status')}")
    lines.extend(
        [
            "",
            "## 信号候选摘要",
            "",
            f"- eligible: {signal_summary.get('eligible_count', 0)}",
            f"- excluded: {signal_summary.get('excluded_count', 0)}",
            f"- display-only: {signal_summary.get('display_only_count', 0)}",
            "",
            "## 实验摘要",
            "",
            f"- applied signals: {experiment.get('applied_signal_count', 0)}",
            f"- excluded signals: {experiment.get('excluded_signal_count', 0)}",
            "",
            "## Readiness Review",
            "",
            f"- needs_more_data: {readiness.get('needs_more_data_count', 0)}",
            f"- rejected_or_blocked: {readiness.get('rejected_or_blocked_count', 0)}",
            f"- manual review items: {manual_queue.get('total_review_items', 0)}",
            "",
            "## 下周证据工作",
            "",
            "- 继续积累 daily run 证据文件。",
            "- 优先补齐缺失历史样本和数据质量 blocked 原因。",
            "- 任何主模型接入仍需单独人工审批和回归测试。",
        ]
    )
    return "\n".join(lines) + "\n"


def run_weekly_research(
    *,
    runs_dir: Path | str,
    output_path: Path | str,
    json_output_path: Path | str,
    days: int = 7,
) -> tuple[Path, Path, dict[str, Any]]:
    root = Path(runs_dir)
    run_dirs = _recent_run_dirs(root, days)
    payload = build_weekly_research_summary(run_dirs=run_dirs, runs_dir=root, days=days)
    json_output = Path(json_output_path)
    markdown_output = Path(output_path)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    markdown_output.write_text(render_weekly_research_markdown(payload), encoding="utf-8")
    return markdown_output, json_output, payload


def build_weekly_research_summary(*, run_dirs: list[Path], runs_dir: Path, days: int) -> dict[str, Any]:
    summaries = [_load_json(path / "daily_research_summary.json") for path in run_dirs]
    summaries = [item for item in summaries if item]
    missing_runs = _missing_run_dates(run_dirs, days)
    reason_counts: Counter[str] = Counter()
    readiness_status: Counter[str] = Counter()
    for summary in summaries:
        reason_counts.update((summary.get("experiment_scoring") or {}).get("top_exclusion_reasons") or {})
        readiness = summary.get("readiness_review") or {}
        for key in ("recommended_for_experiment_count", "needs_more_data_count", "rejected_or_blocked_count"):
            readiness_status[key] += int(readiness.get(key, 0) or 0)
    queue_summary = aggregate_manual_review_queues(run_dirs)
    return {
        "runs_processed": len(summaries),
        "missing_runs": missing_runs,
        "data_quality_trend": [
            {"as_of": item.get("as_of"), "data_quality_grade": item.get("data_quality_grade")}
            for item in summaries
        ],
        "provider_health_trend": [
            {"as_of": item.get("as_of"), "provider_warning_count": (item.get("data_source") or {}).get("provider_warning_count", 0)}
            for item in summaries
        ],
        "signal_eligible_trend": [
            {"as_of": item.get("as_of"), "eligible_count": (item.get("signal_candidates") or {}).get("eligible_count", 0)}
            for item in summaries
        ],
        "top_exclusion_reasons_trend": dict(reason_counts.most_common(10)),
        "applied_signals_trend": [
            {"as_of": item.get("as_of"), "applied_signal_count": (item.get("experiment_scoring") or {}).get("applied_signal_count", 0)}
            for item in summaries
        ],
        "readiness_status_trend": dict(readiness_status),
        "manual_review_queue_summary": queue_summary,
        "recurring_blockers": [reason for reason, count in reason_counts.items() if count > 1],
        "recommendations_for_next_week": [
            "继续积累 daily-research 证据文件。",
            "优先减少 repeated manual review items。",
            "补齐缺失 run 和缺失历史样本后再讨论主模型接入。",
        ],
        "not_production_model": True,
        "no_trading_simulation": True,
    }


def render_weekly_research_markdown(payload: dict[str, Any]) -> str:
    queue = payload.get("manual_review_queue_summary") or {}
    lines = [
        "# Weekly Research Summary",
        "",
        f"- runs_processed: {payload.get('runs_processed')}",
        f"- missing_runs: {', '.join(payload.get('missing_runs') or []) or 'none'}",
        "- 本周汇总只用于证据积累和人工审核，不修改主评分/主风险。",
        "",
        "## Manual Review Queue",
        "",
        f"- total_review_items: {queue.get('total_review_items', 0)}",
        f"- repeated_review_items: {', '.join(queue.get('repeated_review_items') or []) or 'none'}",
        "",
        "## Recurring Blockers",
        "",
    ]
    blockers = payload.get("recurring_blockers") or []
    lines.extend([f"- {item}" for item in blockers] or ["- none"])
    lines.extend(
        [
            "",
            "## Next Week Evidence Work",
            "",
            "- 继续运行 daily-research。",
            "- 聚焦缺失样本、stale cache、warning/degraded window 的证据补齐。",
            "- 主模型接入仍需单独审批和回归测试。",
        ]
    )
    return "\n".join(lines) + "\n"


def aggregate_manual_review_queues(run_dirs: list[Path]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        payload = _load_json(run_dir / "manual_review_queue.json", default=[])
        if isinstance(payload, list):
            items.extend(item for item in payload if isinstance(item, dict))
    by_status = Counter(str(item.get("recommended_status", "unknown")) for item in items)
    by_signal = Counter(str(item.get("signal_id", "unknown")) for item in items)
    unresolved = [
        str(item.get("signal_id", "unknown"))
        for item in items
        if item.get("recommended_status") not in {"rejected", "approved_for_main_candidate"}
    ]
    return {
        "total_review_items": len(items),
        "by_status": dict(by_status),
        "by_signal_id": dict(by_signal),
        "repeated_review_items": sorted(signal for signal, count in by_signal.items() if count > 1),
        "unresolved_items": unresolved,
    }


def _manual_queue_summary(payload: Any) -> dict[str, Any]:
    items = payload if isinstance(payload, list) else []
    by_status = Counter(str(item.get("recommended_status", "unknown")) for item in items if isinstance(item, dict))
    return {
        "total_review_items": len(items),
        "by_status": dict(by_status),
    }


def _warning_summary(warnings: list[dict[str, Any]]) -> dict[str, Any]:
    severity = Counter(str(item.get("severity", "warning")) for item in warnings if isinstance(item, dict))
    codes = Counter(str(item.get("code", "unknown")) for item in warnings if isinstance(item, dict))
    return {
        "total": len(warnings),
        "by_severity": dict(severity),
        "by_code": dict(codes),
    }


def _top_dict(payload: dict[str, Any], limit: int = 5) -> dict[str, Any]:
    counts = Counter({str(key): int(value or 0) for key, value in payload.items()})
    return dict(counts.most_common(limit))


def _recommendation_from_proposal(markdown: str) -> str:
    for line in markdown.splitlines():
        if "是否建议进入主模型" in line:
            separator = "：" if "：" in line else ":"
            value = line.rsplit(separator, 1)[-1].strip()
            return value or "no"
    return "no"


def _recent_run_dirs(runs_dir: Path, days: int) -> list[Path]:
    if not runs_dir.exists():
        return []
    candidates = sorted(path for path in runs_dir.iterdir() if path.is_dir() and _parse_date(path.name))
    if not candidates:
        return []
    end = _parse_date(candidates[-1].name) or date.today()
    start = end - timedelta(days=max(days, 1) - 1)
    return [path for path in candidates if start <= (_parse_date(path.name) or start - timedelta(days=1)) <= end]


def _missing_run_dates(run_dirs: list[Path], days: int) -> list[str]:
    if not run_dirs:
        return []
    dates = sorted(_parse_date(path.name) for path in run_dirs if _parse_date(path.name))
    if not dates:
        return []
    end = dates[-1]
    expected = [end - timedelta(days=offset) for offset in reversed(range(max(days, 1)))]
    available = {item.isoformat() for item in dates}
    return [item.isoformat() for item in expected if item.isoformat() not in available]


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {} if default is None else default


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
