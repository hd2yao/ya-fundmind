from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .config import PortfolioConfig
from .providers import normalize_fund_code


def build_portfolio_analysis_report(
    config: PortfolioConfig,
    *,
    output_dir: Path | str,
    as_of: str | None = None,
) -> dict[str, Any]:
    root = Path(output_dir)
    report = _load_json(root / "fund_agent_report.json")
    market = _load_json(root / "market" / "market_intelligence_report.json")
    resolved_as_of = as_of or report.get("as_of") or market.get("as_of") or date.today().isoformat()
    holdings = list(config.holdings)
    warnings: list[str] = []
    if not holdings:
        warnings.append("portfolio_not_configured")
    market_context = _market_context(market)
    report_positions = _report_positions(report)
    valuation_rows = _report_valuations(report)
    positions = [
        _build_position_row(holding, report_positions, valuation_rows, market_context)
        for holding in holdings
    ]
    valued_positions = [item for item in positions if item.get("current_value") is not None]
    unvalued_position_count = len(positions) - len(valued_positions)
    valuation_status = _valuation_status(len(positions), unvalued_position_count)
    valuations_complete = valuation_status in {"complete", "not_configured"}
    valued_total_value = _round(sum(float(item["current_value"]) for item in valued_positions))
    total_value = valued_total_value if valuations_complete else None
    weights_available = total_value is not None and total_value > 0
    total_cost = _round(sum(float(item["cost_value"] or 0) for item in positions))
    if unvalued_position_count:
        warnings.append("portfolio_current_value_unavailable")
    for item in positions:
        item["weight"] = (
            _round_ratio(float(item["current_value"]) / total_value)
            if weights_available and item.get("current_value") is not None
            else None
        )
        if item.get("target_weight") is not None and item["weight"] is not None:
            item["target_drift"] = _round_ratio(item["weight"] - item["target_weight"])
        else:
            item["target_drift"] = None
    theme_exposure = _build_exposure(positions, key="primary_theme", total_value=total_value)
    fund_type_exposure = _build_exposure(positions, key="fund_type_bucket", total_value=total_value)
    concentration = _build_concentration(positions, weights_available=weights_available)
    observation_issues = _build_observation_issues(positions, theme_exposure, concentration)
    status = "empty" if not holdings else "ok"
    if warnings and status != "empty":
        status = "warning"
    return {
        "schema_version": "1.0",
        "generated_at": _utc_now(),
        "generator": "fund_agent.portfolio_analysis",
        "as_of": resolved_as_of,
        "portfolio_name": config.name,
        "status": status,
        "holding_count": len(holdings),
        "cash_available": float(config.cash_available or 0),
        "total_value": total_value,
        "valued_total_value": valued_total_value,
        "valuation_status": valuation_status,
        "valued_position_count": len(valued_positions),
        "unvalued_position_count": unvalued_position_count,
        "total_cost": total_cost,
        "total_unrealized_return_pct": _round_ratio((total_value / total_cost - 1) * 100) if total_value is not None and total_cost else None,
        "positions": positions,
        "theme_exposure": theme_exposure,
        "fund_type_exposure": fund_type_exposure,
        "concentration": concentration,
        "observation_issues": observation_issues,
        "observation_issue_count": len(observation_issues),
        "warnings": list(dict.fromkeys(warnings)),
        "not_production_model": True,
        "main_score_changed": False,
        "main_risk_changed": False,
    }


def write_portfolio_analysis_outputs(report: dict[str, Any], output_dir: Path | str) -> tuple[Path, Path]:
    root = Path(output_dir)
    portfolio_dir = root / "portfolio"
    portfolio_dir.mkdir(parents=True, exist_ok=True)
    json_path = portfolio_dir / "portfolio_report.json"
    markdown_path = portfolio_dir / "portfolio_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_portfolio_analysis_markdown(report), encoding="utf-8")
    as_of = report.get("as_of")
    if as_of:
        run_dir = root / "runs" / str(as_of)
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "portfolio_report.json").write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
        (run_dir / "portfolio_report.md").write_text(markdown_path.read_text(encoding="utf-8"), encoding="utf-8")
    return json_path, markdown_path


def render_portfolio_analysis_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Portfolio Analysis",
        "",
        f"- as_of: {report.get('as_of')}",
        f"- status: {report.get('status')}",
        f"- holding_count: {report.get('holding_count')}",
        f"- total_value: {report.get('total_value')}",
        f"- valuation_status: {report.get('valuation_status')}",
        f"- total_cost: {report.get('total_cost')}",
        f"- cash_available: {report.get('cash_available')}",
        "- Portfolio Analysis 是组合观察层，不修改主评分/主风险，不构成投资建议。",
        "",
    ]
    if report.get("status") == "empty":
        lines.extend(["## Empty Portfolio", "", "- 未配置持仓。", ""])
    lines.extend(["## Theme Exposure", ""])
    for theme, item in sorted((report.get("theme_exposure") or {}).items()):
        lines.append(f"- {theme}: weight={item.get('weight')} holding_count={item.get('holding_count')}")
    if not report.get("theme_exposure"):
        lines.append("- none")
    lines.extend(["", "## Fund Type Exposure", ""])
    for fund_type, item in sorted((report.get("fund_type_exposure") or {}).items()):
        lines.append(f"- {fund_type}: weight={item.get('weight')} holding_count={item.get('holding_count')}")
    if not report.get("fund_type_exposure"):
        lines.append("- none")
    lines.extend(["", "## Observation Issues", ""])
    lines.extend(
        [
            f"- {item.get('severity')}: {item.get('issue_type')} {item.get('message')}"
            for item in report.get("observation_issues") or []
        ]
        or ["- none"]
    )
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {item}" for item in report.get("warnings") or []] or ["- none"])
    return "\n".join(lines) + "\n"


def _build_position_row(
    holding,
    report_positions: dict[str, dict[str, Any]],
    valuation_rows: dict[str, dict[str, Any]],
    market_context: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    code = normalize_fund_code(holding.code)
    report_row = report_positions.get(code, {})
    valuation = valuation_rows.get(code, {})
    market = market_context.get(code, {})
    cost_value = float(holding.shares) * float(holding.cost_nav)
    current_value = _safe_float(report_row.get("current_value"))
    if current_value is None:
        estimated = _safe_float(valuation.get("estimated_value"))
        current_value = None if estimated is None else float(holding.shares) * estimated
    return {
        "code": code,
        "name": holding.name,
        "shares": float(holding.shares),
        "cost_nav": float(holding.cost_nav),
        "cost_value": _round(cost_value),
        "current_value": _round(current_value) if current_value is not None else None,
        "unrealized_return_pct": _safe_float(report_row.get("unrealized_return_pct")),
        "weight": None,
        "target_weight": holding.target_weight,
        "target_drift": None,
        "buy_date": holding.buy_date,
        "notes": holding.notes,
        "primary_theme": market.get("primary_theme") or "unknown",
        "themes": market.get("themes") or [],
        "fund_type": market.get("fund_type") or "unknown",
        "fund_type_bucket": _fund_type_bucket(market.get("fund_type") or ""),
        "source": market.get("source") or valuation.get("source") or "unknown",
        "valuation_method": valuation.get("method"),
        "valuation_confidence": valuation.get("confidence"),
    }


def _market_context(market: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = {
        normalize_fund_code(item.get("code")): item
        for item in market.get("records") or []
        if isinstance(item, dict)
    }
    classifications = {
        normalize_fund_code(item.get("code")): item
        for item in market.get("classifications") or []
        if isinstance(item, dict)
    }
    context: dict[str, dict[str, Any]] = {}
    for code in set(records) | set(classifications):
        record = records.get(code, {})
        classification = classifications.get(code, {})
        context[code] = {
            "fund_type": record.get("fund_type") or record.get("category"),
            "source": record.get("source"),
            "primary_theme": classification.get("primary_theme"),
            "themes": list(classification.get("themes") or []),
        }
    return context


def _report_positions(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    portfolio = report.get("portfolio") or {}
    return {
        normalize_fund_code(item.get("code")): item
        for item in portfolio.get("positions") or []
        if isinstance(item, dict)
    }


def _report_valuations(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    valuations = report.get("valuations") or {}
    if isinstance(valuations, dict):
        return {normalize_fund_code(key): value for key, value in valuations.items() if isinstance(value, dict)}
    return {
        normalize_fund_code(item.get("code")): item
        for item in valuations
        if isinstance(item, dict)
    }


def _build_exposure(
    positions: list[dict[str, Any]],
    *,
    key: str,
    total_value: float | None,
) -> dict[str, dict[str, Any]]:
    exposure: dict[str, dict[str, Any]] = {}
    for position in positions:
        label = str(position.get(key) or "unknown")
        row = exposure.setdefault(
            label,
            {
                "holding_count": 0,
                "current_value": 0.0,
                "weight": None,
                "codes": [],
                "has_unvalued_position": False,
            },
        )
        row["holding_count"] += 1
        current_value = position.get("current_value")
        if current_value is None:
            row["has_unvalued_position"] = True
        else:
            row["current_value"] = _round(float(row["current_value"]) + float(current_value))
        row["codes"].append(position.get("code"))
    for row in exposure.values():
        has_unvalued_position = bool(row.pop("has_unvalued_position", False))
        if has_unvalued_position:
            row["current_value"] = None
        row["weight"] = (
            _round_ratio(float(row["current_value"]) / total_value)
            if total_value and row["current_value"] is not None
            else None
        )
    return exposure


def _build_concentration(positions: list[dict[str, Any]], *, weights_available: bool) -> dict[str, Any]:
    if not positions:
        return {"top_holding_code": None, "top_holding_weight": 0.0, "hhi": 0.0}
    if not weights_available:
        return {"top_holding_code": None, "top_holding_weight": None, "hhi": None}
    sorted_positions = sorted(positions, key=lambda item: float(item["weight"]), reverse=True)
    return {
        "top_holding_code": sorted_positions[0].get("code"),
        "top_holding_weight": _round_ratio(float(sorted_positions[0].get("weight") or 0)),
        "hhi": _round_ratio(sum(float(item.get("weight") or 0) ** 2 for item in positions)),
    }


def _build_observation_issues(
    positions: list[dict[str, Any]],
    theme_exposure: dict[str, dict[str, Any]],
    concentration: dict[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for theme, row in sorted(theme_exposure.items()):
        if theme != "unknown" and int(row.get("holding_count") or 0) >= 2:
            issues.append(
                {
                    "issue_type": "theme_overlap",
                    "severity": "warning",
                    "message": f"{theme} theme appears in {row.get('holding_count')} holdings.",
                    "metadata": {"theme": theme, "codes": row.get("codes", [])},
                }
            )
    top_weight = _safe_float(concentration.get("top_holding_weight"))
    if top_weight is not None and top_weight > 0.35:
        issues.append(
            {
                "issue_type": "single_holding_concentration",
                "severity": "warning",
                "message": f"{concentration.get('top_holding_code')} concentration is {top_weight:.2%}.",
                "metadata": {"top_holding_code": concentration.get("top_holding_code"), "top_holding_weight": top_weight},
            }
        )
    for position in positions:
        if position.get("current_value") is None:
            issues.append(
                {
                    "issue_type": "missing_position_valuation",
                    "severity": "warning",
                    "message": f"{position.get('code')} has no usable current valuation.",
                    "metadata": {"code": position.get("code")},
                }
            )
    return issues


def _fund_type_bucket(fund_type: str) -> str:
    text = str(fund_type)
    upper = text.upper()
    if "ETF联接" in text or "联接" in text:
        return "ETF联接"
    if "ETF" in upper:
        return "ETF"
    if "QDII" in upper:
        return "QDII"
    if "债" in text:
        return "债券"
    if "货币" in text:
        return "货币"
    if "股票" in text or "混合" in text:
        return "主动权益"
    return "unknown"


def _valuation_status(holding_count: int, unvalued_position_count: int) -> str:
    if not holding_count:
        return "not_configured"
    if unvalued_position_count == holding_count:
        return "unavailable"
    if unvalued_position_count:
        return "partial"
    return "complete"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float) -> float:
    return round(float(value), 2)


def _round_ratio(value: float) -> float:
    return round(float(value), 4)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
