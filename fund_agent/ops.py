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
    market = _latest_market_report(root)
    market_trend = _latest_market_trend(root)
    fund_details = _latest_fund_details(root)
    portfolio = _latest_portfolio_report(root)
    fund_coverage = fund_details.get("coverage_summary") or {}
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
        "market_intelligence_available": bool(market),
        "latest_market_report_path": market.get("_path"),
        "latest_market_as_of": market.get("as_of"),
        "latest_market_total_funds": market.get("total_funds"),
        "latest_market_total_etfs": market.get("total_etfs"),
        "latest_market_theme_count": len(market.get("themes") or []) if market else 0,
        "latest_market_data_quality_grade": (market.get("data_quality_summary") or {}).get("grade") if market else None,
        "market_trend_available": bool(market_trend),
        "latest_market_trend_path": market_trend.get("_path"),
        "latest_market_snapshots_processed": market_trend.get("snapshots_processed", 0) if market_trend else 0,
        "enough_market_history": bool(market_trend.get("enough_market_history", False)) if market_trend else False,
        "latest_market_persistent_hot_count": len(market_trend.get("persistent_hot_themes") or []) if market_trend else 0,
        "latest_market_new_hot_count": len(market_trend.get("new_hot_themes") or []) if market_trend else 0,
        "latest_market_data_quality_trend": market_trend.get("data_quality_trend", []) if market_trend else [],
        "fund_detail_available": bool(fund_details),
        "latest_watchlist_detail_path": fund_details.get("_path"),
        "watchlist_detail_count": fund_details.get("detail_count", 0) if fund_details else 0,
        "watchlist_detail_missing_count": fund_details.get("missing_count", 0) if fund_details else 0,
        "watchlist_detail_warning_count": fund_details.get("warning_count", 0) if fund_details else 0,
        "watchlist_detail_average_coverage_ratio": fund_coverage.get("average_coverage_ratio", 0) if fund_details else 0,
        "watchlist_detail_unknown_theme_count": fund_coverage.get("unknown_theme_count", 0) if fund_details else 0,
        "watchlist_detail_peer_insufficient_count": fund_coverage.get("peer_insufficient_count", 0) if fund_details else 0,
        "latest_fund_detail_as_of": fund_details.get("as_of") if fund_details else None,
        "portfolio_analysis_available": bool(portfolio),
        "latest_portfolio_report_path": portfolio.get("_path"),
        "latest_portfolio_status": portfolio.get("status") if portfolio else None,
        "latest_portfolio_as_of": portfolio.get("as_of") if portfolio else None,
        "latest_portfolio_holding_count": portfolio.get("holding_count", 0) if portfolio else 0,
        "latest_portfolio_total_value": portfolio.get("total_value", 0) if portfolio else 0,
        "latest_portfolio_cash_available": portfolio.get("cash_available", 0) if portfolio else 0,
        "latest_portfolio_observation_issue_count": portfolio.get("observation_issue_count", 0) if portfolio else 0,
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
    market_lines = []
    if status.get("market_intelligence_available"):
        market_lines = [
            "",
            "## Market Intelligence",
            "",
            f"- market_as_of: {status.get('latest_market_as_of')}",
            f"- market_report: {status.get('latest_market_report_path')}",
            f"- market_total_funds: {status.get('latest_market_total_funds')}",
            f"- market_total_etfs: {status.get('latest_market_total_etfs')}",
            f"- market_theme_count: {status.get('latest_market_theme_count')}",
            f"- market_data_quality: {status.get('latest_market_data_quality_grade')}",
            "- 市场观察只用于主题/板块观察，不修改主评分/主风险，不构成投资建议。",
        ]
    trend_lines = []
    if status.get("market_trend_available"):
        trend_lines = [
            "",
            "## Market Trend",
            "",
            f"- market_trend_report: {status.get('latest_market_trend_path')}",
            f"- market_trend_snapshots_processed: {status.get('latest_market_snapshots_processed')}",
            f"- market_trend_enough_history: {status.get('enough_market_history')}",
            f"- market_persistent_hot_count: {status.get('latest_market_persistent_hot_count')}",
            f"- market_new_hot_count: {status.get('latest_market_new_hot_count')}",
            "- 趋势样本不足只影响板块趋势判断，不影响 daily ops/dashboard/market-scan 继续运行。",
        ]
    else:
        trend_lines = [
            "",
            "## Market Trend",
            "",
            "- market_trend_available: False",
            "- Market Trend 尚未运行；不影响 daily ops/dashboard/market-scan 继续运行。",
        ]
    fund_detail_lines = []
    if status.get("fund_detail_available"):
        fund_detail_lines = [
            "",
            "## Watchlist Fund Details",
            "",
            "- fund_detail_available: True",
            f"- detail_count: {status.get('watchlist_detail_count')}",
            f"- missing_count: {status.get('watchlist_detail_missing_count')}",
            f"- warning_count: {status.get('watchlist_detail_warning_count')}",
            f"- average_coverage_ratio: {status.get('watchlist_detail_average_coverage_ratio')}",
            f"- unknown_theme_count: {status.get('watchlist_detail_unknown_theme_count')}",
            f"- peer_insufficient_count: {status.get('watchlist_detail_peer_insufficient_count')}",
            f"- detail_path: {status.get('latest_watchlist_detail_path')}",
            "- Fund Detail 是观察页，不接主评分/主风险，不构成投资建议。",
        ]
    else:
        fund_detail_lines = [
            "",
            "## Watchlist Fund Details",
            "",
            "- fund_detail_available: False",
            "- Fund Detail 尚未运行；不影响 daily ops/dashboard/market-scan 继续运行。",
        ]
    portfolio_lines = []
    if status.get("portfolio_analysis_available"):
        portfolio_lines = [
            "",
            "## Portfolio Analysis",
            "",
            "- portfolio_analysis_available: True",
            f"- portfolio_status: {status.get('latest_portfolio_status')}",
            f"- portfolio_as_of: {status.get('latest_portfolio_as_of')}",
            f"- portfolio_holding_count: {status.get('latest_portfolio_holding_count')}",
            f"- portfolio_total_value: {status.get('latest_portfolio_total_value')}",
            f"- portfolio_cash_available: {status.get('latest_portfolio_cash_available')}",
            f"- portfolio_observation_issue_count: {status.get('latest_portfolio_observation_issue_count')}",
            f"- portfolio_report: {status.get('latest_portfolio_report_path')}",
            "- Portfolio Analysis 是组合观察页，不接主评分/主风险，不构成投资建议。",
        ]
    else:
        portfolio_lines = [
            "",
            "## Portfolio Analysis",
            "",
            "- portfolio_analysis_available: False",
            "- Portfolio Analysis 尚未运行；不影响 daily ops/dashboard 继续运行。",
        ]
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
        *market_lines,
        *trend_lines,
        *fund_detail_lines,
        *portfolio_lines,
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


def _latest_market_report(root: Path) -> dict[str, Any]:
    candidates = [root / "market" / "market_intelligence_report.json"]
    runs_dir = root / "runs"
    if runs_dir.exists():
        candidates.extend(
            path / "market_intelligence_report.json"
            for path in reversed(sorted(item for item in runs_dir.iterdir() if item.is_dir()))
        )
    for path in candidates:
        payload = _load_json(path)
        if payload:
            payload["_path"] = str(path)
            return payload
    return {}


def _latest_market_trend(root: Path) -> dict[str, Any]:
    candidates = [root / "market" / "market_trend_report.json"]
    runs_dir = root / "runs"
    if runs_dir.exists():
        candidates.extend(
            path / "market_trend_report.json"
            for path in reversed(sorted(item for item in runs_dir.iterdir() if item.is_dir()))
        )
    for path in candidates:
        payload = _load_json(path)
        if payload:
            payload["_path"] = str(path)
            return payload
    return {}


def _latest_fund_details(root: Path) -> dict[str, Any]:
    candidates = [root / "fund_details" / "watchlist_fund_details.json"]
    runs_dir = root / "runs"
    if runs_dir.exists():
        candidates.extend(
            path / "fund_details" / "watchlist_fund_details.json"
            for path in reversed(sorted(item for item in runs_dir.iterdir() if item.is_dir()))
        )
    for path in candidates:
        payload = _load_json(path)
        if payload:
            payload["_path"] = str(path)
            return payload
    return {}


def _latest_portfolio_report(root: Path) -> dict[str, Any]:
    candidates = [root / "portfolio" / "portfolio_report.json"]
    runs_dir = root / "runs"
    if runs_dir.exists():
        candidates.extend(
            path / "portfolio_report.json"
            for path in reversed(sorted(item for item in runs_dir.iterdir() if item.is_dir()))
        )
    for path in candidates:
        payload = _load_json(path)
        if payload:
            payload["_path"] = str(path)
            return payload
    return {}
