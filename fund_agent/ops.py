from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_ops_status(output_dir: Path | str) -> dict[str, Any]:
    root = Path(output_dir)
    latest_run = _latest_run(root / "runs")
    artifacts = {
        "daily_summary": _artifact(root / "daily_research_summary.json"),
        "weekly_summary": _artifact(root / "weekly_research_summary.json"),
        "latest_summary": _artifact(root / "latest_summary.md"),
        "dashboard_index": _artifact(root / "dashboard" / "index.html"),
        "dashboard_manifest": _artifact(root / "dashboard" / "manifest.json"),
        "long_horizon_stability": _artifact(root / "long_horizon_stability.json"),
    }
    missing_required = [
        name
        for name in ("daily_summary", "weekly_summary", "long_horizon_stability")
        if not artifacts[name]["exists"]
    ]
    overall = "missing" if missing_required else "ok"
    daily = _load_json(root / "daily_research_summary.json")
    weekly = _load_json(root / "weekly_research_summary.json")
    stability = _load_json(root / "long_horizon_stability.json")
    latest_run_status = latest_run.get("status")
    daily_success = daily.get("status") == "success" or latest_run_status == "success"
    dashboard_ready = artifacts["dashboard_index"]["exists"]
    main_model_blockers = stability.get("main_model_blockers") or stability.get("blockers", [])
    main_model_ready = bool(stability.get("main_model_ready", False))
    blocker_explanation = _main_model_blocker_explanation(main_model_blockers)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(root),
        "overall_status": overall,
        "ops_ready": bool(daily_success),
        "dashboard_ready": dashboard_ready,
        "research_loop_ready": bool(daily_success),
        "latest_run_available": bool(latest_run),
        "latest_run_status": latest_run_status,
        "main_model_ready": main_model_ready,
        "main_model_blockers": main_model_blockers,
        "main_model_blocker_explanation": blocker_explanation,
        "suggested_next_action": _suggested_next_actions(
            ops_ready=bool(daily_success),
            dashboard_ready=dashboard_ready,
            main_model_ready=main_model_ready,
        ),
        "latest_run": latest_run,
        "artifacts": artifacts,
        "daily": {
            "as_of": daily.get("as_of"),
            "status": daily.get("status"),
            "data_quality_grade": daily.get("data_quality_grade"),
            "recommend_main_model": daily.get("recommend_main_model", "no"),
        },
        "weekly": {
            "runs_processed": weekly.get("runs_processed", 0),
            "missing_runs": weekly.get("missing_runs", []),
        },
        "long_horizon": {
            "enough_history": stability.get("enough_history"),
            "blockers": stability.get("blockers", []),
            "main_model_ready": main_model_ready,
            "main_model_blockers": main_model_blockers,
            "readiness_scope": stability.get("readiness_scope", "main_model_promotion_only"),
            "non_blocking_for": stability.get("non_blocking_for", []),
        },
        "not_production_model": True,
        "main_score_changed": False,
        "main_risk_changed": False,
    }


def write_ops_status(status: dict[str, Any], output_path: Path | str) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return output


def write_latest_summary(output_dir: Path | str) -> Path:
    root = Path(output_dir)
    status = build_ops_status(root)
    daily = _load_json(root / "daily_research_summary.json")
    weekly = _load_json(root / "weekly_research_summary.json")
    stability = _load_json(root / "long_horizon_stability.json")
    manual = weekly.get("manual_review_state_summary") or {}
    queue = weekly.get("manual_review_queue_summary") or daily.get("manual_review_queue") or {}
    main_model_blockers = status.get("main_model_blockers") or []
    lines = [
        "# YA FundMind Latest Summary",
        "",
        f"- generated_at: {status['generated_at']}",
        f"- latest_run: {status.get('latest_run', {}).get('as_of') or daily.get('as_of') or '--'}",
        f"- daily_status: {daily.get('status', 'unknown')}",
        f"- ops_ready: {status.get('ops_ready')}",
        f"- dashboard_ready: {status.get('dashboard_ready')}",
        f"- research_loop_ready: {status.get('research_loop_ready')}",
        f"- data_quality_grade: {daily.get('data_quality_grade', 'unknown')}",
        f"- recommend_main_model: {daily.get('recommend_main_model', 'no')}",
        f"- main_model_ready: {status.get('main_model_ready')}",
        f"- main_model_blockers: {', '.join(main_model_blockers) or 'none'}",
        f"- weekly_runs_processed: {weekly.get('runs_processed', 0)}",
        f"- manual_review_items: {queue.get('total_review_items', 0)}",
        f"- manual_needs_more_data: {manual.get('needs_more_data_count', 0)}",
        f"- enough_history: {stability.get('enough_history')}",
        f"- blockers: {', '.join(stability.get('blockers') or []) or 'none'}",
        f"- suggested_next_action: {', '.join(status.get('suggested_next_action') or []) or 'none'}",
        "",
        status.get("main_model_blocker_explanation", ""),
        "",
        "本摘要仅用于本地投研运行状态查看，不修改主评分/主风险，不构成投资建议。",
    ]
    output = root / "latest_summary.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / "latest_summary.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output


def _main_model_blocker_explanation(blockers: list[str]) -> str:
    if "insufficient_history" in blockers:
        return (
            "历史 run 不足只影响主评分/主风险接入判断，不影响 daily research、"
            "dashboard、继续开发和证据积累。"
        )
    if blockers:
        return "当前 blocker 仅用于主模型接入审查；daily ops 和非主模型功能可继续推进。"
    return "当前没有主模型接入 blocker；仍需人工 review gate 后才能考虑主评分/主风险变更。"


def _suggested_next_actions(*, ops_ready: bool, dashboard_ready: bool, main_model_ready: bool) -> list[str]:
    actions: list[str] = []
    if ops_ready:
        actions.append("continue_daily_runs")
    if dashboard_ready:
        actions.append("review_dashboard")
    actions.append("continue_feature_development")
    if not main_model_ready:
        actions.append("do_not_promote_to_main_model_yet")
    return actions


def _latest_run(runs_dir: Path) -> dict[str, Any]:
    if not runs_dir.exists():
        return {}
    run_dirs = sorted(path for path in runs_dir.iterdir() if path.is_dir())
    if not run_dirs:
        return {}
    latest = run_dirs[-1]
    metadata = _load_json(latest / "run_metadata.json")
    return {
        "as_of": metadata.get("as_of", latest.name),
        "status": metadata.get("status"),
        "path": str(latest),
    }


def _artifact(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "updated_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
        if path.exists()
        else None,
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
