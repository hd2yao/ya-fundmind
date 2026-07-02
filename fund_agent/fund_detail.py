from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .cache import FundCache
from .config import load_portfolio_config, load_watchlist_config
from .providers import normalize_fund_code


RETURN_WINDOWS = ("1w", "1m", "3m", "6m", "1y")


@dataclass(frozen=True)
class ReturnWindowView:
    window: str
    total_return: float | None = None
    annualized_return: float | None = None
    max_drawdown: float | None = None
    volatility: float | None = None
    count: int | None = None
    required_points: int | None = None
    actual_points: int | None = None
    data_quality_grade: str = "unknown"
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class MarketRankContext:
    primary_theme: str | None = None
    theme_sample_size: int | None = None
    theme_rank: int | None = None
    rank_in_theme_by_1m_return: int | None = None
    percentile_in_theme_by_1m_return: float | None = None
    rank_in_theme_by_scale: int | None = None
    percentile_in_theme_by_scale: float | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DataCoverageView:
    status: str = "missing"
    coverage_ratio: float = 0.0
    available_fields: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    has_market_record: bool = False
    has_theme_classification: bool = False
    has_nav_history_summary: bool = False
    has_fund_detail: bool = False
    has_cache: bool = False
    return_window_count: int = 0
    required_fields_count: int = 0
    available_fields_count: int = 0
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class PeerComparisonView:
    primary_theme: str = "unknown"
    peer_sample_size: int = 0
    sample_status: str = "unknown"
    rank_by_1m_return: int | None = None
    percentile_by_1m_return: float | None = None
    rank_by_scale: int | None = None
    percentile_by_scale: float | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class SignalContext:
    in_signal_candidates: bool = False
    signal_status: str = "none"
    signal_reasons: tuple[str, ...] = ()
    manual_review_status: str = "none"
    needs_more_data: bool = False
    blocked_or_rejected: bool = False
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class FundDetailView:
    code: str
    name: str = ""
    fund_type: str = ""
    source: str = "unknown"
    as_of: str | None = None
    is_watchlist: bool = False
    is_portfolio: bool = False
    themes: tuple[str, ...] = ()
    primary_theme: str | None = None
    unknown_reason: str = ""
    theme_confidence: float | None = None
    price: float | None = None
    nav: float | None = None
    accumulated_nav: float | None = None
    scale: float | None = None
    fund_company: str | None = None
    fund_manager: str | None = None
    inception_date: str | None = None
    rating: str | None = None
    valuation_date: str | None = None
    exchange_traded: bool = False
    return_windows: dict[str, ReturnWindowView] = field(default_factory=dict)
    nav_history_summary: dict[str, Any] = field(default_factory=dict)
    data_coverage: DataCoverageView = field(default_factory=DataCoverageView)
    peer_comparison: PeerComparisonView = field(default_factory=PeerComparisonView)
    market_rank_context: MarketRankContext = field(default_factory=MarketRankContext)
    signal_context: SignalContext = field(default_factory=SignalContext)
    data_quality_grade: str = "unknown"
    data_quality_warnings: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    observation_notes: tuple[str, ...] = ()
    not_production_model: bool = True


def build_fund_detail_views(
    *,
    codes: Iterable[str],
    output_dir: Path | str,
    watchlist_file: Path | str | None = None,
    portfolio_config: Path | str | None = None,
    cache_file: Path | str | None = None,
) -> list[FundDetailView]:
    root = Path(output_dir)
    normalized_codes = [normalize_fund_code(code) for code in codes if normalize_fund_code(code)]
    artifacts = _load_artifacts(root)
    watchlist_codes = _load_watchlist_codes(watchlist_file)
    watchlist_metadata = _load_watchlist_metadata(watchlist_file)
    portfolio_codes = _load_portfolio_codes(portfolio_config)
    cache_payload = _load_cache_payload(cache_file, normalized_codes)
    return [
        _build_one_detail(
            code=code,
            artifacts=artifacts,
            watchlist_codes=watchlist_codes,
            watchlist_metadata=watchlist_metadata,
            portfolio_codes=portfolio_codes,
            cache_payload=cache_payload,
        )
        for code in normalized_codes
    ]


def fund_detail_to_dict(detail: FundDetailView) -> dict[str, Any]:
    return asdict(detail)


def build_watchlist_fund_details_payload(
    details: list[FundDetailView],
    *,
    detail_dir: Path | str | None = None,
) -> dict[str, Any]:
    warnings = sum(len(item.data_quality_warnings) for item in details)
    missing = sum(1 for item in details if item.missing_fields)
    as_of = next((item.as_of for item in details if item.as_of), None)
    coverage_summary = _build_coverage_summary(details)
    rows: list[dict[str, Any]] = []
    for item in details:
        row = fund_detail_to_dict(item)
        if detail_dir is not None:
            detail_root = Path(detail_dir)
            row["latest_detail_json_path"] = str(detail_root / f"fund_detail_{item.code}.json")
            row["latest_detail_markdown_path"] = str(detail_root / f"fund_detail_{item.code}.md")
        rows.append(row)
    return {
        "schema_version": "1.0",
        "generated_at": _utc_now(),
        "as_of": as_of,
        "detail_count": len(details),
        "missing_count": missing,
        "warning_count": warnings,
        "coverage_summary": coverage_summary,
        "fund_details": rows,
        "not_production_model": True,
        "main_score_changed": False,
        "main_risk_changed": False,
    }


def write_single_fund_detail(
    detail: FundDetailView,
    output_dir: Path | str,
    *,
    json_output: Path | str | None = None,
    summary_output: Path | str | None = None,
) -> tuple[Path, Path]:
    root = Path(output_dir)
    detail_dir = root / "fund_details"
    detail_dir.mkdir(parents=True, exist_ok=True)
    json_path = Path(json_output) if json_output is not None else detail_dir / f"fund_detail_{detail.code}.json"
    md_path = Path(summary_output) if summary_output is not None else detail_dir / f"fund_detail_{detail.code}.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(fund_detail_to_dict(detail), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_fund_detail_markdown(detail), encoding="utf-8")
    _copy_single_to_run(root, detail, json_path, md_path)
    return json_path, md_path


def write_watchlist_fund_details(
    details: list[FundDetailView],
    output_dir: Path | str,
    *,
    json_output: Path | str | None = None,
    summary_output: Path | str | None = None,
) -> tuple[Path, Path]:
    root = Path(output_dir)
    detail_dir = root / "fund_details"
    detail_dir.mkdir(parents=True, exist_ok=True)
    json_path = Path(json_output) if json_output is not None else detail_dir / "watchlist_fund_details.json"
    md_path = Path(summary_output) if summary_output is not None else detail_dir / "watchlist_fund_details.md"
    for detail in details:
        single_json = detail_dir / f"fund_detail_{detail.code}.json"
        single_md = detail_dir / f"fund_detail_{detail.code}.md"
        single_json.write_text(
            json.dumps(fund_detail_to_dict(detail), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        single_md.write_text(render_fund_detail_markdown(detail), encoding="utf-8")
        _copy_single_to_run(root, detail, single_json, single_md)
    payload = build_watchlist_fund_details_payload(details, detail_dir=detail_dir)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_watchlist_fund_details_markdown(details), encoding="utf-8")
    _copy_watchlist_to_run(root, payload.get("as_of"), json_path, md_path)
    return json_path, md_path


def render_fund_detail_markdown(detail: FundDetailView) -> str:
    lines = [
        f"# Fund Detail {detail.code}",
        "",
        f"- 基金代码: {detail.code}",
        f"- 基金名称: {detail.name or '--'}",
        f"- 是否自选池: {detail.is_watchlist}",
        f"- 是否持仓池: {detail.is_portfolio}",
        f"- 基金类型: {detail.fund_type or '--'}",
        f"- 数据源: {detail.source}",
        f"- as_of: {detail.as_of or '--'}",
        f"- 主题归类: {', '.join(detail.themes) or '--'}",
        f"- primary_theme: {detail.primary_theme or '--'}",
        f"- unknown_reason: {detail.unknown_reason or '--'}",
        f"- 主题置信度: {_display(detail.theme_confidence)}",
        "",
        "## 数据覆盖",
        "",
        f"- status: {detail.data_coverage.status}",
        f"- coverage_ratio: {detail.data_coverage.coverage_ratio}",
        f"- available_fields: {', '.join(detail.data_coverage.available_fields) or 'none'}",
        f"- missing_fields: {', '.join(detail.data_coverage.missing_fields) or 'none'}",
        f"- return_window_count: {detail.data_coverage.return_window_count}",
        f"- nav_history_source: {detail.nav_history_summary.get('source', '--') if detail.nav_history_summary else '--'}",
        f"- nav_history_run_type: {detail.nav_history_summary.get('run_type', '--') if detail.nav_history_summary else '--'}",
        f"- nav_history_backfill: {detail.nav_history_summary.get('backfill', False) if detail.nav_history_summary else False}",
        "",
        "## 收益窗口",
        "",
    ]
    for window in RETURN_WINDOWS:
        item = detail.return_windows.get(window)
        if item is None:
            lines.append(f"- {window}: --")
        else:
            lines.append(
                f"- {window}: total_return={_display(item.total_return)} "
                f"grade={item.data_quality_grade} count={_display(item.count)}"
            )
    rank = detail.market_rank_context
    lines.extend(
        [
            "",
            "## 所属主题位置",
            "",
            f"- primary_theme: {rank.primary_theme or '--'}",
            f"- theme_sample_size: {_display(rank.theme_sample_size)}",
            f"- theme_rank: {_display(rank.theme_rank)}",
            f"- rank_in_theme_by_1m_return: {_display(rank.rank_in_theme_by_1m_return)}",
            f"- percentile_in_theme_by_1m_return: {_display(rank.percentile_in_theme_by_1m_return)}",
            f"- rank_in_theme_by_scale: {_display(rank.rank_in_theme_by_scale)}",
            f"- percentile_in_theme_by_scale: {_display(rank.percentile_in_theme_by_scale)}",
            "",
            "## 同主题对比",
            "",
            f"- primary_theme: {detail.peer_comparison.primary_theme}",
            f"- peer_sample_size: {detail.peer_comparison.peer_sample_size}",
            f"- sample_status: {detail.peer_comparison.sample_status}",
            f"- rank_by_1m_return: {_display(detail.peer_comparison.rank_by_1m_return)}",
            f"- percentile_by_1m_return: {_display(detail.peer_comparison.percentile_by_1m_return)}",
            f"- rank_by_scale: {_display(detail.peer_comparison.rank_by_scale)}",
            f"- percentile_by_scale: {_display(detail.peer_comparison.percentile_by_scale)}",
            f"- warnings: {', '.join(detail.peer_comparison.warnings) or 'none'}",
            "",
            "## Signal / Review Context",
            "",
            f"- in_signal_candidates: {detail.signal_context.in_signal_candidates}",
            f"- signal_status: {detail.signal_context.signal_status}",
            f"- manual_review_status: {detail.signal_context.manual_review_status}",
            f"- needs_more_data: {detail.signal_context.needs_more_data}",
            f"- blocked_or_rejected: {detail.signal_context.blocked_or_rejected}",
            "",
            "## 数据质量",
            "",
            f"- data_quality_grade: {detail.data_quality_grade}",
            f"- missing_fields: {', '.join(detail.missing_fields) or 'none'}",
            f"- warnings: {', '.join(detail.data_quality_warnings) or 'none'}",
            "",
            "## 观察说明",
            "",
        ]
    )
    lines.extend([f"- {item}" for item in detail.observation_notes] or ["- 仅用于观察，未进入主评分，未进入主风险。"])
    lines.append("- 仅用于观察，不构成投资建议。")
    return "\n".join(lines) + "\n"


def render_watchlist_fund_details_markdown(details: list[FundDetailView]) -> str:
    payload = build_watchlist_fund_details_payload(details)
    lines = [
        "# Watchlist Fund Details",
        "",
        f"- as_of: {payload.get('as_of') or '--'}",
        f"- detail_count: {payload['detail_count']}",
        f"- missing_count: {payload['missing_count']}",
        f"- warning_count: {payload['warning_count']}",
        f"- average_coverage_ratio: {payload['coverage_summary']['average_coverage_ratio']}",
        f"- unknown_theme_count: {payload['coverage_summary']['unknown_theme_count']}",
        f"- peer_insufficient_count: {payload['coverage_summary']['peer_insufficient_count']}",
        "- Fund Detail 是观察页，不接主评分/主风险，不构成投资建议。",
        "",
        "| 代码 | 名称 | 类型 | 主题 | Coverage | Peer Sample | 数据质量 | return_1m | missing |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for detail in details:
        one_month = detail.return_windows.get("1m")
        lines.append(
            "| {code} | {name} | {fund_type} | {theme} | {coverage} | {peer} | {grade} | {ret} | {missing} |".format(
                code=detail.code,
                name=detail.name or "--",
                fund_type=detail.fund_type or "--",
                theme=detail.primary_theme or "--",
                coverage=detail.data_coverage.status,
                peer=detail.peer_comparison.peer_sample_size,
                grade=detail.data_quality_grade,
                ret=_display(one_month.total_return if one_month else None),
                missing=len(detail.missing_fields),
            )
        )
    return "\n".join(lines) + "\n"


def _build_one_detail(
    *,
    code: str,
    artifacts: dict[str, Any],
    watchlist_codes: set[str],
    watchlist_metadata: dict[str, dict[str, Any]],
    portfolio_codes: set[str],
    cache_payload: dict[str, dict[str, Any]],
) -> FundDetailView:
    market_record = artifacts["records"].get(code, {})
    classification = artifacts["classifications"].get(code, {})
    report_detail = artifacts["report_details"].get(code, {})
    cache = cache_payload.get(code, {})
    nav_summary = artifacts["nav_history_summary"].get(code, {})
    returns = _returns_from(market_record)
    missing_fields: list[str] = []
    warnings: list[str] = []
    unknown_reasons: list[str] = []
    if not market_record:
        missing_fields.append("market_record")
        warnings.append("market artifact missing for fund")
        unknown_reasons.append("missing_market_record")
    name = (
        market_record.get("name")
        or report_detail.get("name")
        or (watchlist_metadata.get(code) or {}).get("name")
        or cache.get("name")
        or ""
    )
    fund_type = (
        market_record.get("fund_type")
        or report_detail.get("fund_type")
        or (watchlist_metadata.get(code) or {}).get("type")
        or cache.get("fund_type")
        or ""
    )
    source = market_record.get("source") or report_detail.get("source") or cache.get("source") or "unknown"
    as_of = market_record.get("as_of") or report_detail.get("as_of") or artifacts.get("as_of") or cache.get("as_of")
    themes = tuple(str(item) for item in classification.get("themes") or ())
    primary_theme = classification.get("primary_theme")
    if not classification:
        unknown_reasons.append("missing_theme_classification")
    primary_theme_unknown = str(primary_theme).strip().lower() == "unknown" if primary_theme is not None else False
    if primary_theme_unknown:
        warnings.append("theme classification unknown")
        unknown_reasons.append("theme_classification_unknown")
    if not primary_theme or primary_theme_unknown:
        missing_fields.append("primary_theme")
        if not primary_theme:
            warnings.append("theme classification missing")
            unknown_reasons.append("missing_primary_theme")
    return_windows = _build_return_windows(returns, nav_summary)
    for window in RETURN_WINDOWS:
        if return_windows[window].total_return is None:
            missing_fields.append(f"return_{window}")
    detail_fields = {
        "fund_company": report_detail.get("fund_company") or cache.get("fund_company"),
        "fund_manager": report_detail.get("fund_manager") or cache.get("fund_manager") or market_record.get("metadata", {}).get("manager"),
        "inception_date": report_detail.get("inception_date") or cache.get("inception_date"),
        "rating": report_detail.get("rating") or cache.get("rating"),
    }
    for field_name, value in detail_fields.items():
        if value in (None, ""):
            missing_fields.append(field_name)
    market_rank = _build_market_rank_context(code, primary_theme, artifacts)
    peer_comparison = _build_peer_comparison_context(code, primary_theme, artifacts)
    signal_context = _build_signal_context(code, artifacts)
    notes = [
        "Fund Detail 是展示层、诊断层、观察层。",
        "未进入主评分，未进入主风险。",
    ]
    if not nav_summary:
        missing_fields.append("nav_history_summary")
        warnings.append("NAV history summary missing")
        notes.append("需要更多 NAV 历史。")
    grade = "normal"
    unique_missing = tuple(dict.fromkeys(missing_fields))
    data_coverage = _build_data_coverage(
        market_record=market_record,
        classification=classification,
        report_detail=report_detail,
        cache=cache,
        nav_summary=nav_summary,
        return_windows=return_windows,
        name=name,
        fund_type=fund_type,
        source=source,
        as_of=as_of,
        detail_fields=detail_fields,
    )
    unique_warnings = tuple(
        dict.fromkeys(
            warnings
            + list(market_rank.warnings)
            + list(peer_comparison.warnings)
            + list(signal_context.warnings)
            + list(data_coverage.warnings)
        )
    )
    if unique_missing or unique_warnings:
        grade = "degraded" if "market_record" in unique_missing else "warning"
    return FundDetailView(
        code=code,
        name=str(name),
        fund_type=str(fund_type),
        source=str(source),
        as_of=str(as_of) if as_of else None,
        is_watchlist=code in watchlist_codes,
        is_portfolio=code in portfolio_codes,
        themes=themes,
        primary_theme=str(primary_theme) if primary_theme else "unknown",
        unknown_reason=",".join(dict.fromkeys(unknown_reasons)),
        theme_confidence=_safe_float(classification.get("confidence")),
        price=_safe_float(market_record.get("price")),
        nav=_safe_float(market_record.get("nav")),
        accumulated_nav=_safe_float(nav_summary.get("latest_accumulated_nav")),
        scale=_safe_float(market_record.get("scale") or report_detail.get("scale") or cache.get("scale")),
        fund_company=detail_fields["fund_company"],
        fund_manager=detail_fields["fund_manager"],
        inception_date=detail_fields["inception_date"],
        rating=detail_fields["rating"],
        valuation_date=market_record.get("valuation_date"),
        exchange_traded=bool(market_record.get("exchange_traded", False)),
        return_windows=return_windows,
        nav_history_summary=nav_summary,
        data_coverage=data_coverage,
        peer_comparison=peer_comparison,
        market_rank_context=market_rank,
        signal_context=signal_context,
        data_quality_grade=grade,
        data_quality_warnings=unique_warnings,
        missing_fields=unique_missing,
        observation_notes=tuple(notes),
    )


def _load_artifacts(root: Path) -> dict[str, Any]:
    market = _load_json(root / "market" / "market_intelligence_report.json")
    candidates = _load_json(root / "market" / "market_fund_candidates.json")
    report = _load_json(root / "fund_agent_report.json")
    backfill_nav = _load_json(root / "backfill" / "nav_history_summary.json")
    signals = _load_json(root / "signal_candidates.json")
    manual_queue = _load_json(root / "manual_review_queue.json", default=[])
    manual_state = _load_json(root / "manual_review_state.json")
    classifications = market.get("classifications") or candidates.get("fund_candidates") or []
    return {
        "as_of": market.get("as_of") or report.get("as_of"),
        "records": {normalize_fund_code(item.get("code")): item for item in market.get("records") or [] if isinstance(item, dict)},
        "classifications": {normalize_fund_code(item.get("code")): item for item in classifications if isinstance(item, dict)},
        "themes": market.get("themes") or [],
        "top_themes": market.get("top_themes") or [],
        "report_details": {normalize_fund_code(item.get("code")): item for item in report.get("fund_details") or [] if isinstance(item, dict)},
        "nav_history_summary": report.get("nav_history_summary") or backfill_nav.get("nav_history_summary") or {},
        "signals": signals,
        "manual_queue": manual_queue if isinstance(manual_queue, list) else [],
        "manual_state": manual_state.get("items") or [],
    }


def _load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {} if default is None else default


def _load_watchlist_codes(path: Path | str | None) -> set[str]:
    if path is None or not Path(path).exists():
        return set()
    try:
        return set(load_watchlist_config(path).codes)
    except Exception:
        return set()


def _load_watchlist_metadata(path: Path | str | None) -> dict[str, dict[str, Any]]:
    if path is None or not Path(path).exists():
        return {}
    rows = _parse_watchlist_items(Path(path))
    return {normalize_fund_code(item.get("code")): dict(item) for item in rows if item.get("code")}


def _parse_watchlist_items(path: Path) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if (
            not stripped
            or stripped.startswith("#")
            or stripped == "funds:"
            or (not raw_line.startswith(" ") and stripped.startswith("name:"))
        ):
            continue
        if stripped.startswith("- "):
            current = {}
            payload.append(current)
            rest = stripped[2:].strip()
            if rest and ":" in rest:
                key, value = rest.split(":", 1)
                current[key.strip()] = value.strip()
            continue
        if current is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            current[key.strip()] = value.strip()
    return payload


def _load_portfolio_codes(path: Path | str | None) -> set[str]:
    if path is None or not Path(path).exists():
        return set()
    try:
        return {item.code for item in load_portfolio_config(path).holdings}
    except Exception:
        return set()


def _load_cache_payload(path: Path | str | None, codes: list[str]) -> dict[str, dict[str, Any]]:
    if path is None or not Path(path).exists():
        return {}
    cache = FundCache(path)
    payload: dict[str, dict[str, Any]] = {}
    for code in codes:
        details = cache.load_fund_details(code=code, allow_stale=True)
        if details:
            detail = details[-1]
            payload[code] = asdict(detail)
            continue
        funds = [fund for fund in cache.load_funds(allow_stale=True) if fund.code == code]
        if funds:
            fund = funds[-1]
            payload[code] = {
                "code": fund.code,
                "name": fund.name,
                "fund_type": fund.category,
                "source": fund.source,
                "as_of": fund.metadata.get("cache_as_of"),
                "scale": fund.scale_billion,
                "fund_manager": fund.manager,
            }
    return payload


def _returns_from(record: dict[str, Any]) -> dict[str, Any]:
    metadata = record.get("metadata") or {}
    returns = metadata.get("returns") or record.get("returns") or {}
    return returns if isinstance(returns, dict) else {}


def _build_return_windows(returns: dict[str, Any], nav_summary: dict[str, Any]) -> dict[str, ReturnWindowView]:
    windows: dict[str, ReturnWindowView] = {}
    nav_windows = nav_summary.get("windows") if isinstance(nav_summary, dict) else {}
    for window in RETURN_WINDOWS:
        summary = (nav_windows or {}).get(window) or {}
        metadata = summary.get("metadata") or {}
        total_return = _safe_float(summary.get("total_return"))
        if total_return is None:
            total_return = _safe_float(returns.get(window))
        warning_list = list(summary.get("warnings") or [])
        grade = summary.get("data_quality_grade") or ("normal" if total_return is not None else "warning")
        if total_return is None:
            warning_list.append("missing_return_window")
        windows[window] = ReturnWindowView(
            window=window,
            total_return=total_return,
            annualized_return=_safe_float(summary.get("annualized_return")),
            max_drawdown=_safe_float(summary.get("max_drawdown")),
            volatility=_safe_float(summary.get("volatility")),
            count=_safe_int(summary.get("count")),
            required_points=_safe_int(metadata.get("required_points")),
            actual_points=_safe_int(metadata.get("actual_points")),
            data_quality_grade=str(grade),
            warnings=tuple(dict.fromkeys(str(item) for item in warning_list)),
        )
    return windows


def _build_market_rank_context(code: str, primary_theme: str | None, artifacts: dict[str, Any]) -> MarketRankContext:
    warnings: list[str] = []
    if not primary_theme:
        return MarketRankContext(warnings=("missing_primary_theme",))
    theme_rows = artifacts.get("themes") or []
    top_rows = artifacts.get("top_themes") or theme_rows
    theme_stat = next((item for item in theme_rows if item.get("theme") == primary_theme), {})
    theme_rank = next((index for index, item in enumerate(top_rows, start=1) if item.get("theme") == primary_theme), None)
    classifications = artifacts.get("classifications") or {}
    records = artifacts.get("records") or {}
    theme_codes = [
        item_code
        for item_code, item in classifications.items()
        if primary_theme in (item.get("themes") or []) or item.get("primary_theme") == primary_theme
    ]
    rank_return = _rank_code(code, theme_codes, records, key=lambda item: _safe_float(_returns_from(item).get("1m")))
    rank_scale = _rank_code(code, theme_codes, records, key=lambda item: _safe_float(item.get("scale")))
    if not theme_codes:
        warnings.append("theme_peer_group_missing")
    return MarketRankContext(
        primary_theme=primary_theme,
        theme_sample_size=_safe_int(theme_stat.get("sample_size")) or len(theme_codes) or None,
        theme_rank=theme_rank,
        rank_in_theme_by_1m_return=rank_return[0],
        percentile_in_theme_by_1m_return=rank_return[1],
        rank_in_theme_by_scale=rank_scale[0],
        percentile_in_theme_by_scale=rank_scale[1],
        warnings=tuple(warnings),
    )


def _build_peer_comparison_context(code: str, primary_theme: str | None, artifacts: dict[str, Any]) -> PeerComparisonView:
    if not primary_theme:
        return PeerComparisonView(warnings=("missing_primary_theme",))
    classifications = artifacts.get("classifications") or {}
    records = artifacts.get("records") or {}
    theme_codes = [
        item_code
        for item_code, item in classifications.items()
        if primary_theme in (item.get("themes") or []) or item.get("primary_theme") == primary_theme
    ]
    sample_size = len(theme_codes)
    rank_return = _rank_code(code, theme_codes, records, key=lambda item: _safe_float(_returns_from(item).get("1m")))
    rank_scale = _rank_code(code, theme_codes, records, key=lambda item: _safe_float(item.get("scale")))
    warnings: list[str] = []
    if sample_size <= 0:
        sample_status = "unknown"
        warnings.append("theme_peer_group_missing")
    elif sample_size < 2:
        sample_status = "insufficient"
        warnings.append("peer_sample_insufficient")
    else:
        sample_status = "sufficient"
    return PeerComparisonView(
        primary_theme=str(primary_theme),
        peer_sample_size=sample_size,
        sample_status=sample_status,
        rank_by_1m_return=rank_return[0],
        percentile_by_1m_return=rank_return[1],
        rank_by_scale=rank_scale[0],
        percentile_by_scale=rank_scale[1],
        warnings=tuple(warnings),
    )


def _build_data_coverage(
    *,
    market_record: dict[str, Any],
    classification: dict[str, Any],
    report_detail: dict[str, Any],
    cache: dict[str, Any],
    nav_summary: dict[str, Any],
    return_windows: dict[str, ReturnWindowView],
    name: Any,
    fund_type: Any,
    source: Any,
    as_of: Any,
    detail_fields: dict[str, Any],
) -> DataCoverageView:
    available: list[str] = []
    checks = {
        "market_record": bool(market_record),
        "theme_classification": bool(classification),
        "name": bool(name),
        "fund_type": bool(fund_type),
        "source": bool(source and source != "unknown"),
        "as_of": bool(as_of),
        "return_1m": return_windows.get("1m") is not None and return_windows["1m"].total_return is not None,
        "return_3m": return_windows.get("3m") is not None and return_windows["3m"].total_return is not None,
        "return_6m": return_windows.get("6m") is not None and return_windows["6m"].total_return is not None,
        "return_1y": return_windows.get("1y") is not None and return_windows["1y"].total_return is not None,
        "nav_history_summary": bool(nav_summary),
        "fund_company": bool(detail_fields.get("fund_company")),
        "fund_manager": bool(detail_fields.get("fund_manager")),
        "inception_date": bool(detail_fields.get("inception_date")),
        "rating": bool(detail_fields.get("rating")),
    }
    for field_name, present in checks.items():
        if present:
            available.append(field_name)
    missing = [field_name for field_name, present in checks.items() if not present]
    required_count = len(checks)
    available_count = len(available)
    ratio = round(available_count / required_count, 4) if required_count else 0.0
    if ratio >= 0.8:
        status = "complete"
    elif ratio >= 0.5:
        status = "partial"
    elif ratio > 0:
        status = "sparse"
    else:
        status = "missing"
    warnings: list[str] = []
    if status in {"missing", "sparse"}:
        warnings.append("fund_detail_coverage_low")
    return DataCoverageView(
        status=status,
        coverage_ratio=ratio,
        available_fields=tuple(available),
        missing_fields=tuple(missing),
        has_market_record=bool(market_record),
        has_theme_classification=bool(classification),
        has_nav_history_summary=bool(nav_summary),
        has_fund_detail=bool(report_detail),
        has_cache=bool(cache),
        return_window_count=sum(1 for item in return_windows.values() if item.total_return is not None),
        required_fields_count=required_count,
        available_fields_count=available_count,
        warnings=tuple(warnings),
    )


def _build_coverage_summary(details: list[FundDetailView]) -> dict[str, Any]:
    total = len(details)
    ratios = [item.data_coverage.coverage_ratio for item in details]
    status_counts: dict[str, int] = {}
    for item in details:
        status_counts[item.data_coverage.status] = status_counts.get(item.data_coverage.status, 0) + 1
    return {
        "total_count": total,
        "average_coverage_ratio": round(sum(ratios) / total, 4) if total else 0.0,
        "complete_count": status_counts.get("complete", 0),
        "partial_count": status_counts.get("partial", 0),
        "sparse_count": status_counts.get("sparse", 0),
        "missing_coverage_count": status_counts.get("missing", 0),
        "unknown_theme_count": sum(1 for item in details if item.primary_theme == "unknown"),
        "peer_insufficient_count": sum(
            1 for item in details if item.peer_comparison.sample_status in {"insufficient", "unknown"}
        ),
    }


def _rank_code(code: str, codes: list[str], records: dict[str, dict[str, Any]], *, key) -> tuple[int | None, float | None]:
    values = [(item_code, key(records.get(item_code, {}))) for item_code in codes]
    values = [(item_code, value) for item_code, value in values if value is not None]
    values.sort(key=lambda item: item[1], reverse=True)
    for index, (item_code, _) in enumerate(values, start=1):
        if item_code == code:
            return index, _percentile(index, len(values))
    return None, None


def _build_signal_context(code: str, artifacts: dict[str, Any]) -> SignalContext:
    signals = artifacts.get("signals") or {}
    status = "none"
    reasons: list[str] = []
    in_candidates = False
    for field_name, label in (
        ("eligible_signals", "eligible"),
        ("excluded_signals", "excluded"),
        ("display_only_signals", "display_only"),
    ):
        for item in signals.get(field_name) or []:
            if normalize_fund_code(item.get("code")) == code or code in str(item.get("signal_id", "")):
                in_candidates = True
                status = label
                reason = item.get("excluded_reason") or item.get("evidence") or item.get("signal_id")
                if reason:
                    reasons.append(str(reason))
    review_status = "none"
    needs_more_data = False
    blocked_or_rejected = False
    for item in artifacts.get("manual_queue") or []:
        if code in str(item.get("signal_id", "")) or code in str(item.get("reason", "")):
            review_status = str(item.get("recommended_status") or "queued")
            needs_more_data = needs_more_data or review_status in {"needs_data", "needs_more_data"}
            reasons.append(str(item.get("reason") or item.get("review_id")))
    for item in artifacts.get("manual_state") or []:
        if code in str(item.get("signal_id", "")) or code in str(item.get("review_id", "")):
            review_status = str(item.get("status") or review_status)
            needs_more_data = needs_more_data or review_status == "needs_more_data"
            blocked_or_rejected = blocked_or_rejected or review_status == "rejected"
    return SignalContext(
        in_signal_candidates=in_candidates,
        signal_status=status,
        signal_reasons=tuple(dict.fromkeys(reasons)),
        manual_review_status=review_status,
        needs_more_data=needs_more_data,
        blocked_or_rejected=blocked_or_rejected,
    )


def _copy_single_to_run(root: Path, detail: FundDetailView, json_path: Path, md_path: Path) -> None:
    if not detail.as_of:
        return
    day_dir = root / "runs" / detail.as_of
    if not day_dir.exists():
        return
    run_dir = day_dir / "fund_details"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / json_path.name).write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    (run_dir / md_path.name).write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")


def _copy_watchlist_to_run(root: Path, as_of: str | None, json_path: Path, md_path: Path) -> None:
    if not as_of:
        return
    run_dir = root / "runs" / as_of / "fund_details"
    if not (root / "runs" / as_of).exists():
        return
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "watchlist_fund_details.json").write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    (run_dir / "watchlist_fund_details.md").write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")


def _percentile(rank: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round((total - rank + 1) / total, 4)


def _safe_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def _display(value: Any) -> str:
    return "--" if value is None else str(value)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
