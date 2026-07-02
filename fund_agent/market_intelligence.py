from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any, Iterable

from .models import FundRecord


RETURN_WINDOWS = ("1w", "1m", "3m", "6m", "1y")
WRAPPER_THEMES = {"ETF联接", "LOF", "QDII", "货币"}
BROAD_THEMES = {"宽基"}


@dataclass(frozen=True)
class MarketFundRecord:
    code: str
    name: str
    fund_type: str
    source: str
    as_of: str
    price: float | None = None
    nav: float | None = None
    scale: float | None = None
    valuation_date: str | None = None
    exchange_traded: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketThemeRule:
    name: str
    keywords: tuple[str, ...] = ()
    fund_types: tuple[str, ...] = ()
    metadata_keywords: tuple[str, ...] = ()
    exchange_traded: bool | None = None


@dataclass(frozen=True)
class MarketThemeClassification:
    code: str
    name: str
    themes: tuple[str, ...]
    primary_theme: str
    classification_rules: tuple[str, ...]
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketThemeStats:
    theme: str
    fund_count: int
    etf_count: int
    active_fund_count: int
    sample_size: int
    avg_return_1w: float | None = None
    avg_return_1m: float | None = None
    avg_return_3m: float | None = None
    avg_return_6m: float | None = None
    avg_return_1y: float | None = None
    median_return_1m: float | None = None
    positive_ratio_1m: float | None = None
    scale_total: float | None = None
    scale_median: float | None = None
    data_quality_grade: str = "unknown"
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketIntelligenceReport:
    schema_version: str
    generated_at: str
    as_of: str
    source: str
    run_type: str
    total_funds: int
    total_etfs: int
    themes: tuple[dict[str, Any], ...]
    top_themes: tuple[dict[str, Any], ...]
    hot_theme_candidates: tuple[dict[str, Any], ...]
    insufficient_sample_themes: tuple[dict[str, Any], ...]
    data_quality_summary: dict[str, Any]
    warnings: tuple[str, ...]
    not_production_model: bool = True
    main_score_changed: bool = False
    main_risk_changed: bool = False
    records: tuple[dict[str, Any], ...] = ()
    classifications: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class MarketIntelligenceOutputs:
    report_path: Path
    summary_path: Path
    theme_rankings_path: Path
    fund_candidates_path: Path
    snapshot_path: Path
    run_report_path: Path
    run_summary_path: Path
    run_theme_rankings_path: Path
    run_fund_candidates_path: Path
    run_snapshot_path: Path


@dataclass(frozen=True)
class MarketThemeTrend:
    theme: str
    snapshots_count: int
    first_seen: str | None
    last_seen: str | None
    latest_rank: int | None
    previous_rank: int | None
    rank_change: int | None
    latest_sample_size: int | None
    sample_size_change: int | None
    latest_hot: bool
    hot_days: int
    hot_ratio: float
    latest_data_quality_grade: str
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketTrendReport:
    schema_version: str
    generated_at: str
    period_days: int
    snapshots_processed: int
    minimum_required_snapshots: int
    enough_market_history: bool
    source: str | None
    latest_as_of: str | None
    theme_trends: tuple[dict[str, Any], ...]
    rising_themes: tuple[dict[str, Any], ...]
    falling_themes: tuple[dict[str, Any], ...]
    persistent_hot_themes: tuple[dict[str, Any], ...]
    new_hot_themes: tuple[dict[str, Any], ...]
    disappeared_hot_themes: tuple[dict[str, Any], ...]
    insufficient_history_themes: tuple[dict[str, Any], ...]
    data_quality_trend: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]
    run_type_counts: dict[str, int] = field(default_factory=dict)
    backfill_snapshot_count: int = 0
    not_production_model: bool = True


@dataclass(frozen=True)
class MarketTrendOutputs:
    report_path: Path
    summary_path: Path
    rankings_path: Path
    run_report_path: Path | None = None
    run_summary_path: Path | None = None


def fund_record_to_market_record(fund: FundRecord, *, as_of: str) -> MarketFundRecord:
    return MarketFundRecord(
        code=fund.code,
        name=fund.name,
        fund_type=fund.category,
        source=fund.source,
        as_of=as_of,
        price=fund.price,
        nav=fund.nav,
        scale=fund.scale_billion,
        valuation_date=fund.valuation_date or fund.nav_date,
        exchange_traded=fund.exchange_traded,
        metadata={
            **fund.metadata,
            "returns": dict(fund.returns),
            "manager": fund.manager,
            "target_etf": fund.target_etf,
            "proxy_symbol": fund.proxy_symbol,
        },
    )


def load_market_theme_rules(path: Path | str = Path("configs/market_themes.yaml")) -> tuple[MarketThemeRule, ...]:
    config_path = Path(path)
    if not config_path.exists():
        return _default_theme_rules()
    text = config_path.read_text(encoding="utf-8").strip()
    if not text:
        return _default_theme_rules()
    if text.startswith("{") or text.startswith("["):
        payload = json.loads(text)
        rows = payload.get("themes", payload) if isinstance(payload, dict) else payload
    else:
        rows = _parse_theme_yaml(config_path)
    rules = tuple(_theme_rule_from_mapping(item) for item in rows if isinstance(item, dict))
    return rules or _default_theme_rules()


def classify_market_fund(
    record: MarketFundRecord,
    rules: Iterable[MarketThemeRule],
) -> MarketThemeClassification:
    haystack_parts = [
        record.name,
        record.fund_type,
        str(record.exchange_traded),
    ]
    for value in record.metadata.values():
        if isinstance(value, (str, int, float, bool)):
            haystack_parts.append(str(value))
    haystack = " ".join(haystack_parts).lower()
    matches: list[tuple[str, int, str]] = []
    for rule in rules:
        score = 0
        reasons: list[str] = []
        for keyword in rule.keywords:
            if keyword and keyword.lower() in haystack:
                score += 2
                reasons.append(f"keyword:{keyword}")
        for fund_type in rule.fund_types:
            if fund_type and fund_type.lower() in record.fund_type.lower():
                score += 1
                reasons.append(f"fund_type:{fund_type}")
        for keyword in rule.metadata_keywords:
            if keyword and keyword.lower() in haystack:
                score += 1
                reasons.append(f"metadata:{keyword}")
        if rule.exchange_traded is not None and rule.exchange_traded == record.exchange_traded:
            score += 1
            reasons.append(f"exchange_traded:{rule.exchange_traded}")
        if score > 0:
            matches.append((rule.name, score, ",".join(reasons)))
    if not matches:
        return MarketThemeClassification(
            code=record.code,
            name=record.name,
            themes=("unknown",),
            primary_theme="unknown",
            classification_rules=(),
            confidence=0.0,
            metadata={"reason": "no_rule_matched"},
        )
    matches.sort(key=lambda item: (-_primary_score(item[0], item[1]), item[0]))
    themes = tuple(dict.fromkeys(item[0] for item in matches))
    primary = themes[0]
    confidence = min(1.0, round(0.4 + matches[0][1] * 0.15, 2))
    return MarketThemeClassification(
        code=record.code,
        name=record.name,
        themes=themes,
        primary_theme=primary,
        classification_rules=tuple(item[2] for item in matches if item[2]),
        confidence=confidence,
        metadata={"match_scores": {theme: score for theme, score, _ in matches}},
    )


def build_market_intelligence_report(
    records: Iterable[MarketFundRecord],
    *,
    as_of: str | None = None,
    source: str,
    themes_config: Path | str = Path("configs/market_themes.yaml"),
    top_n: int = 20,
    min_theme_sample_size: int = 5,
    run_type: str = "market_scan",
) -> MarketIntelligenceReport:
    resolved_as_of = as_of or date.today().isoformat()
    rows = tuple(records)
    rules = load_market_theme_rules(themes_config)
    classifications = tuple(classify_market_fund(record, rules) for record in rows)
    by_code = {record.code: record for record in rows}
    by_theme: dict[str, list[MarketFundRecord]] = defaultdict(list)
    for classification in classifications:
        for theme in classification.themes:
            by_theme[theme].append(by_code[classification.code])
    stats = tuple(
        _build_theme_stats(theme, items, min_theme_sample_size=min_theme_sample_size)
        for theme, items in sorted(by_theme.items())
    )
    stat_dicts = tuple(_theme_stats_dict(item) for item in stats)
    top_themes = tuple(_sort_theme_stats(stat_dicts)[: max(top_n, 0)])
    hot_candidates = tuple(
        item
        for item in top_themes
        if item["sample_size"] >= min_theme_sample_size and item.get("avg_return_1m") is not None
    )
    insufficient = tuple(
        item for item in stat_dicts if item["sample_size"] < min_theme_sample_size and item["theme"] != "unknown"
    )
    data_quality_summary = _build_data_quality_summary(rows, stat_dicts)
    warnings = tuple(data_quality_summary.get("warnings", []))
    return MarketIntelligenceReport(
        schema_version="1.0",
        generated_at=datetime.now(timezone.utc).isoformat(),
        as_of=resolved_as_of,
        source=source,
        run_type=run_type,
        total_funds=len(rows),
        total_etfs=sum(1 for record in rows if _is_etf(record)),
        themes=stat_dicts,
        top_themes=top_themes,
        hot_theme_candidates=hot_candidates,
        insufficient_sample_themes=insufficient,
        data_quality_summary=data_quality_summary,
        warnings=warnings,
        records=tuple(asdict(record) for record in rows),
        classifications=tuple(asdict(item) for item in classifications),
    )


def render_market_intelligence_summary(report: MarketIntelligenceReport) -> str:
    lines = [
        "# Market Intelligence Summary",
        "",
        f"- 运行日期: {report.as_of}",
        f"- 数据源: {report.source}",
        f"- 全市场基金数量: {report.total_funds}",
        f"- ETF 数量: {report.total_etfs}",
        f"- 主题覆盖数量: {len(report.themes)}",
        f"- 数据质量: {report.data_quality_summary.get('grade', 'unknown')}",
        "- 这是市场观察，不是买卖建议。",
        "- 本阶段不接入主评分/主风险，不改变主报告结论。",
        "",
        "## 热门主题候选",
        "",
    ]
    if report.hot_theme_candidates:
        for item in report.hot_theme_candidates:
            lines.append(
                "- {theme}: sample_size={sample} avg_return_1m={ret}".format(
                    theme=item.get("theme"),
                    sample=item.get("sample_size"),
                    ret=_display_number(item.get("avg_return_1m")),
                )
            )
    else:
        lines.append("- none")
    lines.extend(["", "## 样本不足主题", ""])
    if report.insufficient_sample_themes:
        for item in report.insufficient_sample_themes:
            lines.append(f"- {item.get('theme')}: sample_size={item.get('sample_size')}")
    else:
        lines.append("- none")
    lines.extend(["", "## 数据质量摘要", ""])
    lines.append(f"- missing_return_windows: {', '.join(report.data_quality_summary.get('missing_return_windows') or []) or 'none'}")
    lines.append(f"- stale_record_count: {report.data_quality_summary.get('stale_record_count', 0)}")
    lines.extend(["", "## 主题归类警告", ""])
    lines.extend([f"- {item}" for item in report.warnings] or ["- none"])
    return "\n".join(lines) + "\n"


def write_market_intelligence_outputs(
    report: MarketIntelligenceReport,
    output_dir: Path | str,
) -> MarketIntelligenceOutputs:
    root = Path(output_dir)
    market_dir = root / "market"
    snapshots_dir = market_dir / "snapshots"
    run_dir = root / "runs" / report.as_of
    market_dir.mkdir(parents=True, exist_ok=True)
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    report_payload = market_report_to_dict(report)
    snapshot_payload = build_market_snapshot(report)
    rankings = {
        "schema_version": "1.0",
        "generated_at": report.generated_at,
        "as_of": report.as_of,
        "source": report.source,
        "top_themes": report.top_themes,
        "hot_theme_candidates": report.hot_theme_candidates,
        "insufficient_sample_themes": report.insufficient_sample_themes,
        "not_production_model": True,
    }
    candidates = {
        "schema_version": "1.0",
        "generated_at": report.generated_at,
        "as_of": report.as_of,
        "source": report.source,
        "fund_candidates": report.classifications,
        "not_production_model": True,
        "candidate_layer_only": True,
    }
    summary = render_market_intelligence_summary(report)
    paths = MarketIntelligenceOutputs(
        report_path=market_dir / "market_intelligence_report.json",
        summary_path=market_dir / "market_intelligence_summary.md",
        theme_rankings_path=market_dir / "market_theme_rankings.json",
        fund_candidates_path=market_dir / "market_fund_candidates.json",
        snapshot_path=snapshots_dir / f"{report.as_of}.json",
        run_report_path=run_dir / "market_intelligence_report.json",
        run_summary_path=run_dir / "market_intelligence_summary.md",
        run_theme_rankings_path=run_dir / "market_theme_rankings.json",
        run_fund_candidates_path=run_dir / "market_fund_candidates.json",
        run_snapshot_path=run_dir / "market_snapshot.json",
    )
    for path, payload in (
        (paths.report_path, report_payload),
        (paths.theme_rankings_path, rankings),
        (paths.fund_candidates_path, candidates),
        (paths.snapshot_path, snapshot_payload),
        (paths.run_report_path, report_payload),
        (paths.run_theme_rankings_path, rankings),
        (paths.run_fund_candidates_path, candidates),
        (paths.run_snapshot_path, snapshot_payload),
    ):
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    paths.summary_path.write_text(summary, encoding="utf-8")
    paths.run_summary_path.write_text(summary, encoding="utf-8")
    return paths


def market_report_to_dict(report: MarketIntelligenceReport) -> dict[str, Any]:
    return asdict(report)


def build_market_snapshot(report: MarketIntelligenceReport) -> dict[str, Any]:
    return {
        "schema_version": report.schema_version,
        "generated_at": report.generated_at,
        "as_of": report.as_of,
        "source": report.source,
        "provider": report.source,
        "run_type": report.run_type,
        "total_funds": report.total_funds,
        "total_etfs": report.total_etfs,
        "theme_count": len(report.themes),
        "hot_theme_count": len(report.hot_theme_candidates),
        "data_quality_grade": report.data_quality_summary.get("grade", "unknown"),
        "theme_rankings": list(report.top_themes),
        "hot_theme_candidates": list(report.hot_theme_candidates),
        "insufficient_sample_themes": list(report.insufficient_sample_themes),
        "data_quality_summary": report.data_quality_summary,
        "warnings": list(report.warnings),
        "not_production_model": True,
        "market_observation_only": True,
    }


def build_market_trend_report(
    market_dir: Path | str,
    *,
    days: int = 30,
    min_snapshots: int = 3,
    top_n: int = 20,
) -> MarketTrendReport:
    snapshots = _load_market_snapshots(Path(market_dir), days=days)
    processed = len(snapshots)
    run_type_counts = Counter(str(snapshot.get("run_type") or "unknown") for snapshot in snapshots)
    backfill_snapshot_count = run_type_counts.get("historical_backfill", 0)
    enough_history = processed >= max(min_snapshots, 1)
    latest = snapshots[-1] if snapshots else {}
    latest_as_of = str(latest.get("as_of")) if latest.get("as_of") else None
    previous_as_of = str(snapshots[-2].get("as_of")) if processed >= 2 and snapshots[-2].get("as_of") else None
    theme_history: dict[str, list[dict[str, Any]]] = defaultdict(list)
    hot_by_date: dict[str, set[str]] = {}

    for snapshot in snapshots:
        as_of = str(snapshot.get("as_of") or "")
        hot_themes = {_theme_name(item) for item in snapshot.get("hot_theme_candidates") or []}
        hot_themes.discard("")
        hot_by_date[as_of] = hot_themes
        rankings = _snapshot_theme_rankings(snapshot)
        for rank, item in enumerate(rankings, start=1):
            theme = _theme_name(item)
            if not theme:
                continue
            theme_history[theme].append(
                {
                    "as_of": as_of,
                    "rank": rank,
                    "sample_size": _safe_int(item.get("sample_size")),
                    "hot": theme in hot_themes,
                    "data_quality_grade": str(item.get("data_quality_grade") or snapshot.get("data_quality_grade") or "unknown"),
                    "warnings": tuple(str(value) for value in (item.get("warnings") or [])),
                    "raw": item,
                }
            )

    trends = tuple(
        _build_theme_trend(
            theme,
            history,
            snapshots_processed=processed,
            latest_as_of=latest_as_of,
            previous_as_of=previous_as_of,
        )
        for theme, history in sorted(theme_history.items())
    )
    trend_dicts = tuple(
        sorted(
            (asdict(item) for item in trends),
            key=lambda item: (
                item.get("latest_rank") is None,
                item.get("latest_rank") or 999999,
                -(item.get("hot_ratio") or 0),
                item.get("theme"),
            ),
        )
    )
    rising = tuple(
        sorted(
            (item for item in trend_dicts if item.get("latest_rank") is not None and (item.get("rank_change") or 0) > 0),
            key=lambda item: (-(item.get("rank_change") or 0), item.get("latest_rank") or 999999, item.get("theme")),
        )[: max(top_n, 0)]
    )
    falling = tuple(
        sorted(
            (item for item in trend_dicts if item.get("latest_rank") is not None and (item.get("rank_change") or 0) < 0),
            key=lambda item: ((item.get("rank_change") or 0), item.get("latest_rank") or 999999, item.get("theme")),
        )[: max(top_n, 0)]
    )
    persistent = tuple(
        sorted(
            (
                item
                for item in trend_dicts
                if item.get("latest_hot") and item.get("hot_days", 0) >= 2
            ),
            key=lambda item: (-(item.get("hot_ratio") or 0), item.get("latest_rank") or 999999, item.get("theme")),
        )[: max(top_n, 0)]
    )
    latest_hot = hot_by_date.get(latest_as_of or "", set())
    previous_hot = hot_by_date.get(previous_as_of or "", set())
    new_hot = tuple(
        sorted(
            (item for item in trend_dicts if item.get("theme") in latest_hot and item.get("theme") not in previous_hot),
            key=lambda item: (item.get("latest_rank") or 999999, item.get("theme")),
        )[: max(top_n, 0)]
        if processed >= 2
        else ()
    )
    disappeared = tuple(
        sorted(
            (item for item in trend_dicts if item.get("theme") in previous_hot and item.get("theme") not in latest_hot),
            key=lambda item: (item.get("previous_rank") or 999999, item.get("theme")),
        )[: max(top_n, 0)]
        if processed >= 2
        else ()
    )
    insufficient = tuple(
        sorted(
            (item for item in trend_dicts if item.get("snapshots_count", 0) < max(min_snapshots, 1)),
            key=lambda item: (item.get("snapshots_count", 0), item.get("latest_rank") or 999999, item.get("theme")),
        )[: max(top_n, 0)]
    )
    warnings: list[str] = []
    if not enough_history:
        warnings.append(
            f"insufficient_market_history: snapshots_processed={processed} minimum_required={max(min_snapshots, 1)}"
        )
    if not snapshots:
        warnings.append("no_market_snapshots_found")
    return MarketTrendReport(
        schema_version="1.0",
        generated_at=datetime.now(timezone.utc).isoformat(),
        period_days=max(days, 1),
        snapshots_processed=processed,
        minimum_required_snapshots=max(min_snapshots, 1),
        enough_market_history=enough_history,
        source=latest.get("source") or latest.get("provider"),
        latest_as_of=latest_as_of,
        theme_trends=trend_dicts,
        rising_themes=rising,
        falling_themes=falling,
        persistent_hot_themes=persistent,
        new_hot_themes=new_hot,
        disappeared_hot_themes=disappeared,
        insufficient_history_themes=insufficient,
        data_quality_trend=_build_market_data_quality_trend(snapshots),
        warnings=tuple(warnings),
        run_type_counts=dict(run_type_counts),
        backfill_snapshot_count=backfill_snapshot_count,
        not_production_model=True,
    )


def write_market_trend_outputs(report: MarketTrendReport, output_dir: Path | str) -> MarketTrendOutputs:
    root = Path(output_dir)
    market_dir = root / "market"
    market_dir.mkdir(parents=True, exist_ok=True)
    report_payload = market_trend_report_to_dict(report)
    rankings = {
        "schema_version": report.schema_version,
        "generated_at": report.generated_at,
        "latest_as_of": report.latest_as_of,
        "period_days": report.period_days,
        "theme_trends": report.theme_trends,
        "rising_themes": report.rising_themes,
        "falling_themes": report.falling_themes,
        "persistent_hot_themes": report.persistent_hot_themes,
        "new_hot_themes": report.new_hot_themes,
        "disappeared_hot_themes": report.disappeared_hot_themes,
        "run_type_counts": report.run_type_counts,
        "backfill_snapshot_count": report.backfill_snapshot_count,
        "not_production_model": True,
    }
    summary = render_market_trend_summary(report)
    report_path = market_dir / "market_trend_report.json"
    summary_path = market_dir / "market_trend_summary.md"
    rankings_path = market_dir / "theme_trend_rankings.json"
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    rankings_path.write_text(json.dumps(rankings, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    summary_path.write_text(summary, encoding="utf-8")
    run_report_path = None
    run_summary_path = None
    if report.latest_as_of:
        run_dir = root / "runs" / report.latest_as_of
        if run_dir.exists():
            run_report_path = run_dir / "market_trend_report.json"
            run_summary_path = run_dir / "market_trend_summary.md"
            run_report_path.write_text(
                json.dumps(report_payload, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            run_summary_path.write_text(summary, encoding="utf-8")
    return MarketTrendOutputs(
        report_path=report_path,
        summary_path=summary_path,
        rankings_path=rankings_path,
        run_report_path=run_report_path,
        run_summary_path=run_summary_path,
    )


def market_trend_report_to_dict(report: MarketTrendReport) -> dict[str, Any]:
    return asdict(report)


def render_market_trend_summary(report: MarketTrendReport) -> str:
    lines = [
        "# Market Trend Summary",
        "",
        f"- latest_as_of: {report.latest_as_of or '--'}",
        f"- period_days: {report.period_days}",
        f"- snapshots_processed: {report.snapshots_processed}",
        f"- minimum_required_snapshots: {report.minimum_required_snapshots}",
        f"- enough_market_history: {report.enough_market_history}",
        f"- backfill_snapshot_count: {report.backfill_snapshot_count}",
        f"- run_type_counts: {_format_run_type_counts(report.run_type_counts)}",
        "- 这是市场趋势观察，不是买卖建议。",
        "- 本阶段不接入主评分/主风险，不改变主报告结论。",
        "",
    ]
    if not report.enough_market_history:
        lines.extend(
            [
                "## 趋势样本不足",
                "",
                "- 趋势样本不足，但 Market Intelligence 可继续运行。",
                "- 当前结果可作为当日横截面观察，不能视为稳定板块趋势。",
                "",
            ]
        )
    lines.extend(["## 持续热门主题", ""])
    lines.extend(_theme_summary_lines(report.persistent_hot_themes, empty="- none"))
    lines.extend(["", "## 新增热门主题", ""])
    lines.extend(_theme_summary_lines(report.new_hot_themes, empty="- none"))
    lines.extend(["", "## 排名上升主题", ""])
    lines.extend(_theme_summary_lines(report.rising_themes, empty="- none"))
    lines.extend(["", "## 排名下降主题", ""])
    lines.extend(_theme_summary_lines(report.falling_themes, empty="- none"))
    lines.extend(["", "## 数据质量趋势", ""])
    if report.data_quality_trend:
        for item in report.data_quality_trend:
            lines.append(
                "- {as_of}: grade={grade} insufficient_sample={insufficient} warnings={warnings}".format(
                    as_of=item.get("as_of"),
                    grade=item.get("data_quality_grade"),
                    insufficient=item.get("insufficient_sample_theme_count"),
                    warnings=item.get("warning_count"),
                )
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {item}" for item in report.warnings] or ["- none"])
    return "\n".join(lines) + "\n"


def _load_market_snapshots(market_dir: Path, *, days: int) -> tuple[dict[str, Any], ...]:
    snapshots_dir = market_dir / "snapshots"
    if not snapshots_dir.exists():
        return ()
    rows = []
    for path in sorted(snapshots_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        as_of = str(payload.get("as_of") or path.stem)
        parsed = _parse_snapshot_date(as_of)
        if parsed is None:
            continue
        payload["_path"] = str(path)
        payload["_as_of_date"] = parsed
        rows.append(payload)
    if not rows:
        return ()
    rows.sort(key=lambda item: item["_as_of_date"])
    latest = rows[-1]["_as_of_date"]
    start = latest - timedelta(days=max(days, 1) - 1)
    filtered = [item for item in rows if start <= item["_as_of_date"] <= latest]
    for item in filtered:
        item.pop("_as_of_date", None)
    return tuple(filtered)


def _build_theme_trend(
    theme: str,
    history: list[dict[str, Any]],
    *,
    snapshots_processed: int,
    latest_as_of: str | None,
    previous_as_of: str | None,
) -> MarketThemeTrend:
    history = sorted(history, key=lambda item: item.get("as_of") or "")
    by_as_of = {item.get("as_of"): item for item in history}
    latest_entry = by_as_of.get(latest_as_of) if latest_as_of else None
    previous_entry = by_as_of.get(previous_as_of) if previous_as_of else None
    if latest_entry is not None and previous_entry is None:
        earlier = [item for item in history if item is not latest_entry]
        previous_entry = earlier[-1] if earlier else None
    rank_change = None
    sample_size_change = None
    if latest_entry is not None and previous_entry is not None:
        rank_change = _safe_int(previous_entry.get("rank")) - _safe_int(latest_entry.get("rank"))
        sample_size_change = _safe_int(latest_entry.get("sample_size")) - _safe_int(previous_entry.get("sample_size"))
    hot_days = sum(1 for item in history if item.get("hot"))
    latest_hot = bool(latest_entry and latest_entry.get("hot"))
    warnings: list[str] = []
    for item in history:
        warnings.extend(str(value) for value in (item.get("warnings") or ()))
    if latest_entry is None and latest_as_of:
        warnings.append("theme_not_seen_in_latest_snapshot")
    quality_entry = latest_entry or (history[-1] if history else {})
    return MarketThemeTrend(
        theme=theme,
        snapshots_count=len(history),
        first_seen=str(history[0].get("as_of")) if history else None,
        last_seen=str(history[-1].get("as_of")) if history else None,
        latest_rank=_safe_int(latest_entry.get("rank")) if latest_entry else None,
        previous_rank=_safe_int(previous_entry.get("rank")) if previous_entry else None,
        rank_change=rank_change,
        latest_sample_size=_safe_int(latest_entry.get("sample_size")) if latest_entry else None,
        sample_size_change=sample_size_change,
        latest_hot=latest_hot,
        hot_days=hot_days,
        hot_ratio=round(hot_days / snapshots_processed, 4) if snapshots_processed else 0.0,
        latest_data_quality_grade=str(quality_entry.get("data_quality_grade", "unknown")),
        warnings=tuple(dict.fromkeys(warnings)),
        metadata={
            "observation_only": True,
            "not_production_model": True,
            "latest_snapshot_as_of": latest_as_of,
        },
    )


def _build_market_data_quality_trend(snapshots: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    rows = []
    for snapshot in snapshots:
        summary = snapshot.get("data_quality_summary") or {}
        warnings = snapshot.get("warnings") or []
        rows.append(
            {
                "as_of": snapshot.get("as_of"),
                "data_quality_grade": snapshot.get("data_quality_grade") or summary.get("grade", "unknown"),
                "unknown_theme_count": _safe_int(summary.get("unknown_theme_count")),
                "insufficient_sample_theme_count": _safe_int(
                    summary.get("insufficient_sample_theme_count")
                    or len(snapshot.get("insufficient_sample_themes") or [])
                ),
                "warning_count": len(warnings),
            }
        )
    return tuple(rows)


def _snapshot_theme_rankings(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rankings = snapshot.get("theme_rankings") or snapshot.get("top_themes") or snapshot.get("themes") or []
    return [item for item in rankings if isinstance(item, dict) and _theme_name(item)]


def _theme_summary_lines(items: tuple[dict[str, Any], ...], *, empty: str) -> list[str]:
    if not items:
        return [empty]
    rows = []
    for item in items:
        rows.append(
            "- {theme}: latest_rank={rank} rank_change={change} hot_days={hot_days} hot_ratio={hot_ratio}".format(
                theme=item.get("theme"),
                rank=_display_number(item.get("latest_rank")),
                change=_display_number(item.get("rank_change")),
                hot_days=item.get("hot_days", 0),
                hot_ratio=item.get("hot_ratio", 0),
            )
        )
    return rows


def _format_run_type_counts(value: dict[str, int]) -> str:
    if not value:
        return "none"
    return ", ".join(f"{key}={count}" for key, count in sorted(value.items()))


def _theme_name(item: dict[str, Any]) -> str:
    return str(item.get("theme") or "").strip()


def _parse_snapshot_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _build_theme_stats(
    theme: str,
    records: list[MarketFundRecord],
    *,
    min_theme_sample_size: int,
) -> MarketThemeStats:
    returns = {window: _return_values(records, window) for window in RETURN_WINDOWS}
    one_month = returns["1m"]
    scales = [record.scale for record in records if record.scale is not None]
    warnings: list[str] = []
    if len(records) < min_theme_sample_size:
        warnings.append("insufficient_sample")
    missing_windows = [window for window, values in returns.items() if not values]
    if missing_windows:
        warnings.append("missing_return_windows:" + ",".join(missing_windows))
    grade = "normal"
    if warnings:
        grade = "degraded" if len(records) < min_theme_sample_size else "warning"
    return MarketThemeStats(
        theme=theme,
        fund_count=len(records),
        etf_count=sum(1 for record in records if _is_etf(record)),
        active_fund_count=sum(1 for record in records if not _is_etf(record)),
        sample_size=len(records),
        avg_return_1w=_mean(returns["1w"]),
        avg_return_1m=_mean(one_month),
        avg_return_3m=_mean(returns["3m"]),
        avg_return_6m=_mean(returns["6m"]),
        avg_return_1y=_mean(returns["1y"]),
        median_return_1m=round(float(median(one_month)), 4) if one_month else None,
        positive_ratio_1m=round(sum(1 for value in one_month if value > 0) / len(one_month), 4) if one_month else None,
        scale_total=round(sum(scales), 4) if scales else None,
        scale_median=round(float(median(scales)), 4) if scales else None,
        data_quality_grade=grade,
        warnings=tuple(warnings),
        metadata={"min_theme_sample_size": min_theme_sample_size},
    )


def _build_data_quality_summary(
    records: tuple[MarketFundRecord, ...],
    theme_stats: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    missing_windows = [
        window
        for window in RETURN_WINDOWS
        if not any(_return_value(record, window) is not None for record in records)
    ]
    stale_count = sum(1 for record in records if record.metadata.get("stale"))
    unknown_theme_count = sum(1 for item in theme_stats if item.get("theme") == "unknown")
    insufficient_sample_theme_count = sum(
        1 for item in theme_stats if "insufficient_sample" in (item.get("warnings") or [])
    )
    warnings: list[str] = []
    if missing_windows:
        warnings.append("missing_return_windows:" + ",".join(missing_windows))
    if stale_count:
        warnings.append(f"stale_records:{stale_count}")
    if insufficient_sample_theme_count:
        warnings.append(f"insufficient_sample_themes:{insufficient_sample_theme_count}")
    grade = "normal"
    if missing_windows or stale_count or unknown_theme_count or insufficient_sample_theme_count:
        grade = "warning"
    if not records:
        grade = "degraded"
        warnings.append("empty_market_universe")
    return {
        "grade": grade,
        "missing_return_windows": missing_windows,
        "stale_record_count": stale_count,
        "unknown_theme_count": unknown_theme_count,
        "insufficient_sample_theme_count": insufficient_sample_theme_count,
        "records_with_return_1m": sum(1 for record in records if _return_value(record, "1m") is not None),
        "warnings": warnings,
        "observation_only": True,
    }


def _theme_stats_dict(stats: MarketThemeStats) -> dict[str, Any]:
    return asdict(stats)


def _primary_score(theme: str, score: int) -> int:
    return score - 2 if theme in WRAPPER_THEMES else score


def _is_etf(record: MarketFundRecord) -> bool:
    text = f"{record.name} {record.fund_type}".upper()
    return "ETF" in text


def _sort_theme_stats(items: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (
            item.get("theme") in BROAD_THEMES,
            item.get("avg_return_1m") is None,
            -(item.get("avg_return_1m") or -999999),
            -int(item.get("sample_size") or 0),
            str(item.get("theme")),
        ),
    )


def _return_values(records: list[MarketFundRecord], window: str) -> list[float]:
    return [value for record in records if (value := _return_value(record, window)) is not None]


def _return_value(record: MarketFundRecord, window: str) -> float | None:
    returns = record.metadata.get("returns") or {}
    if not isinstance(returns, dict):
        return None
    value = returns.get(window)
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _display_number(value: object) -> str:
    if value is None:
        return "--"
    return str(value)


def _theme_rule_from_mapping(item: dict[str, Any]) -> MarketThemeRule:
    return MarketThemeRule(
        name=str(item.get("name", "")).strip(),
        keywords=_split_list(item.get("keywords")),
        fund_types=_split_list(item.get("fund_types")),
        metadata_keywords=_split_list(item.get("metadata_keywords")),
        exchange_traded=item.get("exchange_traded") if isinstance(item.get("exchange_traded"), bool) else None,
    )


def _split_list(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return tuple(item.strip() for item in str(value).split(",") if item.strip())


def _parse_theme_yaml(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped == "themes:":
            continue
        if stripped.startswith("- "):
            current = {}
            rows.append(current)
            rest = stripped[2:].strip()
            if rest:
                key, value = _split_key_value(rest)
                current[key] = _parse_scalar(value)
            continue
        if current is not None and ":" in stripped:
            key, value = _split_key_value(stripped)
            current[key] = _parse_scalar(value)
            continue
        raise ValueError(f"Unsupported market theme YAML line in {path}: {raw_line}")
    return rows


def _split_key_value(text: str) -> tuple[str, str]:
    key, value = text.split(":", 1)
    return key.strip(), value.strip()


def _parse_scalar(value: str) -> object:
    text = value.strip()
    if not text:
        return ""
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    lower = text.lower()
    if lower in {"true", "false"}:
        return lower == "true"
    return text


def _default_theme_rules() -> tuple[MarketThemeRule, ...]:
    return (
        MarketThemeRule("宽基", keywords=("沪深300", "中证500", "中证1000", "创业板", "科创", "上证50")),
        MarketThemeRule("沪深300", keywords=("沪深300", "HS300", "300ETF")),
        MarketThemeRule("中证500", keywords=("中证500", "500ETF")),
        MarketThemeRule("中证1000", keywords=("中证1000", "1000ETF")),
        MarketThemeRule("创业板", keywords=("创业板", "创业板指")),
        MarketThemeRule("科创", keywords=("科创", "科创板")),
        MarketThemeRule("半导体", keywords=("半导体",)),
        MarketThemeRule("芯片", keywords=("芯片",)),
        MarketThemeRule("人工智能", keywords=("人工智能", "AI", "智能")),
        MarketThemeRule("机器人", keywords=("机器人",)),
        MarketThemeRule("医药", keywords=("医药", "医疗", "生物")),
        MarketThemeRule("创新药", keywords=("创新药",)),
        MarketThemeRule("消费", keywords=("消费", "食品饮料")),
        MarketThemeRule("白酒", keywords=("白酒",)),
        MarketThemeRule("新能源", keywords=("新能源", "电池", "电动车")),
        MarketThemeRule("光伏", keywords=("光伏",)),
        MarketThemeRule("储能", keywords=("储能",)),
        MarketThemeRule("军工", keywords=("军工", "国防")),
        MarketThemeRule("港股", keywords=("港股", "香港", "恒生")),
        MarketThemeRule("恒生科技", keywords=("恒生科技", "HSTECH")),
        MarketThemeRule("纳指", keywords=("纳斯达克", "纳指", "NASDAQ")),
        MarketThemeRule("标普500", keywords=("标普500", "S&P500")),
        MarketThemeRule("黄金", keywords=("黄金",)),
        MarketThemeRule("债券", keywords=("债",), fund_types=("债券",)),
        MarketThemeRule("红利", keywords=("红利",)),
        MarketThemeRule("低波", keywords=("低波",)),
        MarketThemeRule("QDII", fund_types=("QDII",), keywords=("QDII",)),
        MarketThemeRule("货币", fund_types=("货币",), keywords=("货币",)),
        MarketThemeRule("LOF", fund_types=("LOF",), keywords=("LOF",)),
        MarketThemeRule("ETF联接", fund_types=("ETF联接",), keywords=("ETF联接", "联接")),
    )
