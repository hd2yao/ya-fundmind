from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from .artifacts import ArtifactCatalog
from .contract import validate_contract_file, validate_output_dir
from .research_copilot import ResearchCopilot
from .research_query import ResearchQueryService


REQUIRED_RUN_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("fund_agent_report.json", "report"),
    ("snapshot.json", "snapshot"),
    ("provider_trace.json", "trace"),
)
REQUIRED_RUN_FILES = ("daily_research_summary.json", "run_metadata.json")
REQUIRED_RUN_STEPS = ("daily", "validate_contract")
PERFORMANCE_BUDGETS_MS = {
    "catalog_scan": 750.0,
    "market_query": 1200.0,
    "market_answer": 2000.0,
}
NON_LIVE_PROVIDERS = {"fixture", "demo", "synthetic", "cache:fixture"}
OBSERVATION_MODES = {"historical_compat", "post_rc"}
SCHEDULER_TRIGGERS = {"daily_ops", "launchd", "scheduler"}


def evaluate_release_readiness(
    output_dir: Path | str,
    *,
    minimum_valid_runs: int = 3,
    release_target: str = "v2.0.0-rc.1",
    observation_mode: str = "historical_compat",
    required_app_version: str | None = None,
    required_git_commit: str | None = None,
) -> dict[str, Any]:
    mode = str(observation_mode)
    if mode not in OBSERVATION_MODES:
        raise ValueError(f"unsupported observation mode: {observation_mode}")
    root = Path(output_dir)
    runs_dir = root / "runs"
    run_dirs = sorted(
        path
        for path in runs_dir.iterdir()
        if path.is_dir() and _parse_date(path.name) is not None
    ) if runs_dir.exists() else []
    observations = [
        inspect_run_bundle(
            path,
            observation_mode=mode,
            required_app_version=required_app_version,
            required_git_commit=required_git_commit,
        )
        for path in run_dirs
    ]
    valid = [item for item in observations if item["status"] == "valid"]

    contract_summary = _contract_summary(root)
    performance = _measure_performance(root)
    blockers: list[str] = []
    if str(release_target) == "v2.0.0" and mode != "post_rc":
        blockers.append("final_release_requires_post_rc_observation")
    if mode == "post_rc" and not required_app_version:
        blockers.append("required_app_version_missing")
    if mode == "post_rc" and not required_git_commit:
        blockers.append("required_git_commit_missing")
    if len(valid) < max(int(minimum_valid_runs), 1):
        blockers.append("insufficient_valid_release_runs")
    if not contract_summary["ok"]:
        blockers.append("contract_validation_failed")
    if not performance["within_budget"]:
        blockers.append("performance_budget_failed")

    excluded = [item for item in observations if item["status"] != "valid"]
    warnings = []
    if excluded:
        warnings.append(f"excluded_run_count:{len(excluded)}")
    warnings.extend(performance.get("warnings") or [])
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "fund_agent",
        "release_target": str(release_target),
        "observation_mode": mode,
        "required_provenance": {
            "app_version": required_app_version,
            "git_commit": required_git_commit,
            "git_dirty": False if mode == "post_rc" else None,
            "triggers": sorted(SCHEDULER_TRIGGERS) if mode == "post_rc" else [],
        },
        "status": "pass" if not blockers else "fail",
        "minimum_valid_runs": max(int(minimum_valid_runs), 1),
        "valid_run_count": len(valid),
        "observed_run_dates": [str(item["as_of"]) for item in valid],
        "run_observations": observations,
        "contract_summary": contract_summary,
        "performance": performance,
        "boundaries": {
            "not_production_model": True,
            "main_score_changed": False,
            "main_risk_changed": False,
            "trading_enabled": False,
        },
        "blockers": blockers,
        "warnings": warnings,
    }


def inspect_run_bundle(
    run_dir: Path | str,
    *,
    observation_mode: str = "historical_compat",
    required_app_version: str | None = None,
    required_git_commit: str | None = None,
) -> dict[str, Any]:
    root = Path(run_dir)
    reasons: list[str] = []
    run_date = _parse_date(root.name)
    if run_date is None:
        reasons.append("invalid_run_date")

    for filename in REQUIRED_RUN_FILES:
        if not (root / filename).is_file():
            reasons.append(f"required_artifact_missing:{filename}")
    for filename, _ in REQUIRED_RUN_ARTIFACTS:
        if not (root / filename).is_file():
            reasons.append(f"required_artifact_missing:{filename}")

    summary = _load_json(root / "daily_research_summary.json")
    metadata = _load_json(root / "run_metadata.json")
    if summary is None:
        reasons.append("daily_summary_invalid")
        summary = {}
    if metadata is None:
        reasons.append("run_metadata_invalid")
        metadata = {}

    as_of = str(summary.get("as_of") or root.name)
    if run_date is not None and as_of != root.name:
        reasons.append("run_date_mismatch")
    if summary.get("status") != "success":
        reasons.append("daily_summary_not_success")
    if metadata.get("status") != "success":
        reasons.append("run_metadata_not_success")

    provenance = metadata.get("provenance")
    if observation_mode == "post_rc":
        if not isinstance(provenance, dict):
            reasons.append("run_provenance_missing")
            provenance = {}
        if required_app_version and provenance.get("app_version") != required_app_version:
            reasons.append("run_app_version_mismatch")
        if required_git_commit and provenance.get("git_commit") != required_git_commit:
            reasons.append("run_git_commit_mismatch")
        if provenance.get("git_dirty") is not False:
            reasons.append("run_git_dirty")
        if provenance.get("trigger") not in SCHEDULER_TRIGGERS:
            reasons.append("run_trigger_not_scheduler")
    elif not isinstance(provenance, dict):
        provenance = {}

    step_status = {
        str(item.get("step_name")): str(item.get("status"))
        for item in metadata.get("steps") or []
        if isinstance(item, dict) and item.get("step_name")
    }
    for step in REQUIRED_RUN_STEPS:
        status = step_status.get(step)
        if status is None:
            reasons.append(f"required_step_missing:{step}")
        elif status != "success":
            reasons.append(f"required_step_failed:{step}")

    if summary.get("missing_artifacts"):
        reasons.append("daily_missing_artifacts")
    quality = str(summary.get("data_quality_grade") or "unknown")
    if quality not in {"normal", "warning"}:
        reasons.append(f"data_quality_{quality}")
    if summary.get("not_production_model") is not True:
        reasons.append("not_production_model_boundary_missing")
    if summary.get("main_score_changed") is not False:
        reasons.append("main_score_changed")
    if summary.get("main_risk_changed") is not False:
        reasons.append("main_risk_changed")

    providers = _provider_health(summary)
    provider_names = sorted(
        {str(item.get("provider") or "unknown") for item in providers}
    )
    if not providers:
        reasons.append("provider_health_missing")
    if not provider_names or any(_is_non_live_provider(name) for name in provider_names):
        reasons.append("non_live_provider")
    live_rows = sum(_non_negative_int(item.get("live_row_count")) for item in providers)
    if live_rows <= 0:
        reasons.append("provider_live_rows_missing")
    fallback_used = any(item.get("fallback_used") is True for item in providers)
    if fallback_used:
        reasons.append("provider_fallback_used")
    provider_warnings = [
        warning
        for provider in providers
        for warning in provider.get("warnings") or []
        if isinstance(warning, dict)
    ]
    if any(str(item.get("severity") or "").lower() in {"critical", "error"} for item in provider_warnings):
        reasons.append("critical_provider_warning")

    contract_status: dict[str, bool] = {}
    for filename, contract_type in REQUIRED_RUN_ARTIFACTS:
        path = root / filename
        if not path.is_file():
            continue
        result = validate_contract_file(path, contract_type, strict=True)
        contract_status[contract_type] = result.ok
        if not result.ok:
            reasons.append(f"artifact_contract_invalid:{filename}")

    return {
        "as_of": as_of,
        "status": "valid" if not reasons else "excluded",
        "data_quality_grade": quality,
        "providers": provider_names,
        "provider_live_row_count": live_rows,
        "provider_fallback_used": fallback_used,
        "provider_warning_count": len(provider_warnings),
        "contract_status": contract_status,
        "provenance": provenance,
        "reasons": _deduplicate(reasons),
    }


def write_release_readiness(result: dict[str, Any], path: Path | str) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output


def _contract_summary(output_dir: Path) -> dict[str, Any]:
    results = validate_output_dir(output_dir, strict=True).results
    failures = [
        {
            "contract_type": item.contract_type,
            "path": str(item.path),
            "errors": list(item.errors),
        }
        for item in results
        if not item.ok
    ]
    return {
        "ok": bool(results) and not failures,
        "files_checked": len(results),
        "failures": failures,
    }


def _measure_performance(output_dir: Path) -> dict[str, Any]:
    measurements: dict[str, float] = {}
    warnings: list[str] = []
    statuses: dict[str, str] = {}

    def measure(name: str, operation) -> Any:
        started = perf_counter()
        value = operation()
        measurements[name] = round((perf_counter() - started) * 1000, 3)
        return value

    try:
        descriptors = measure("catalog_scan", lambda: ArtifactCatalog(output_dir).scan())
        statuses["catalog_scan"] = "ok" if descriptors else "unavailable"
        context = measure("market_query", lambda: ResearchQueryService(output_dir).query("market"))
        statuses["market_query"] = context.status
        answer = measure(
            "market_answer",
            lambda: ResearchCopilot(output_dir).answer("今天市场和热门板块有什么变化？"),
        )
        statuses["market_answer"] = answer.answer_status
    except Exception as exc:  # release boundary must report, not crash
        warnings.append(f"performance_probe_failed:{type(exc).__name__}")

    available = (
        statuses.get("catalog_scan") == "ok"
        and statuses.get("market_query") in {"ok", "partial"}
        and statuses.get("market_answer") in {"answered", "partial"}
    )
    within = available and all(
        measurements.get(name, float("inf")) <= budget
        for name, budget in PERFORMANCE_BUDGETS_MS.items()
    )
    return {
        "within_budget": within,
        "measurements_ms": measurements,
        "budgets_ms": dict(PERFORMANCE_BUDGETS_MS),
        "statuses": statuses,
        "warnings": warnings,
    }


def _provider_health(summary: dict[str, Any]) -> list[dict[str, Any]]:
    data_source = summary.get("data_source")
    if not isinstance(data_source, dict):
        return []
    providers = data_source.get("provider_health")
    if not isinstance(providers, list):
        return []
    return [item for item in providers if isinstance(item, dict)]


def _is_non_live_provider(provider: str) -> bool:
    normalized = provider.strip().lower()
    return (
        normalized in NON_LIVE_PROVIDERS
        or normalized.startswith("cache:")
        or "fixture" in normalized
        or "synthetic" in normalized
    )


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _non_negative_int(value: Any) -> int:
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _deduplicate(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))
