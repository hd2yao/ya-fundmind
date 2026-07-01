from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
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
    run_report_path: Path
    run_summary_path: Path
    run_theme_rankings_path: Path
    run_fund_candidates_path: Path


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
    run_dir = root / "runs" / report.as_of
    market_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    report_payload = market_report_to_dict(report)
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
        run_report_path=run_dir / "market_intelligence_report.json",
        run_summary_path=run_dir / "market_intelligence_summary.md",
        run_theme_rankings_path=run_dir / "market_theme_rankings.json",
        run_fund_candidates_path=run_dir / "market_fund_candidates.json",
    )
    for path, payload in (
        (paths.report_path, report_payload),
        (paths.theme_rankings_path, rankings),
        (paths.fund_candidates_path, candidates),
        (paths.run_report_path, report_payload),
        (paths.run_theme_rankings_path, rankings),
        (paths.run_fund_candidates_path, candidates),
    ):
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    paths.summary_path.write_text(summary, encoding="utf-8")
    paths.run_summary_path.write_text(summary, encoding="utf-8")
    return paths


def market_report_to_dict(report: MarketIntelligenceReport) -> dict[str, Any]:
    return asdict(report)


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
