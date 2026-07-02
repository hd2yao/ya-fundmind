from __future__ import annotations

import html
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .research_loop import aggregate_manual_review_queues
from .review_state import list_review_state, summarize_review_state


PAGES = ("index.html", "runs.html", "signals.html", "review.html", "data_quality.html", "market.html", "funds.html")


def generate_evidence_dashboard(
    *,
    runs_dir: Path | str,
    review_state_path: Path | str,
    output_dir: Path | str,
    days: int = 30,
) -> Path:
    run_dirs = _recent_run_dirs(Path(runs_dir), days)
    summaries = [_load_json(path / "daily_research_summary.json") for path in run_dirs]
    summaries = [item for item in summaries if item]
    review_items = list_review_state(review_state_path)
    queue_summary = aggregate_manual_review_queues(run_dirs)
    state_summary = summarize_review_state(review_items)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    context = {
        "run_dirs": run_dirs,
        "summaries": summaries,
        "review_items": review_items,
        "queue_summary": queue_summary,
        "state_summary": state_summary,
        "market_report": _latest_market_report(run_dirs, output),
        "market_trend": _latest_market_trend(output),
        "fund_details": _latest_fund_details(output),
    }
    _write_page(output / "index.html", "Evidence Dashboard", _index_body(context))
    _write_page(output / "runs.html", "Runs", _runs_body(context))
    _write_page(output / "signals.html", "Signals", _signals_body(context))
    _write_page(output / "review.html", "Manual Review", _review_body(context))
    _write_page(output / "data_quality.html", "Data Quality", _data_quality_body(context))
    _write_page(output / "market.html", "Market Intelligence", _market_body(context))
    _write_page(output / "funds.html", "Watchlist Fund Details", _funds_body(context))
    _write_fund_detail_pages(output, context.get("fund_details") or {})
    manifest = {
        "schema_version": "1.0",
        "generator": "fund_agent",
        "not_production_model": True,
        "runs_processed": len(summaries),
        "pages": list(PAGES),
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return manifest_path


def _write_page(path: Path, title: str, body: str) -> None:
    path.write_text(
        "\n".join(
            [
                "<!doctype html>",
                "<html><head><meta charset=\"utf-8\"><title>{}</title></head>".format(html.escape(title)),
                "<body>",
                "<nav><a href=\"index.html\">Index</a> <a href=\"runs.html\">Runs</a> <a href=\"signals.html\">Signals</a> <a href=\"review.html\">Review</a> <a href=\"data_quality.html\">Data Quality</a> <a href=\"market.html\">Market</a> <a href=\"funds.html\">Funds</a></nav>",
                "<p><strong>not_production_model=true</strong></p>",
                body,
                "</body></html>",
            ]
        ),
        encoding="utf-8",
    )


def _index_body(context: dict[str, Any]) -> str:
    summaries = context["summaries"]
    latest = summaries[-1] if summaries else {}
    market_report = context.get("market_report") or {}
    market_trend = context.get("market_trend") or {}
    fund_details = context.get("fund_details") or {}
    research_ready = str(bool(latest.get("status") == "success")).lower()
    dashboard_ready = "true"
    return """
<h1>Evidence Dashboard</h1>
<ul>
  <li>runs_processed: {runs}</li>
  <li>latest_status: {status}</li>
  <li>data_quality: {quality}</li>
  <li>applied_signals: {applied}</li>
  <li>recommend_main_model: no</li>
  <li>research_loop_ready: {research_ready}</li>
  <li>dashboard_ready: {dashboard_ready}</li>
  <li>market_intelligence_available: {market_available}</li>
  <li>market_trend_available: {trend_available}</li>
  <li>market_trend_snapshots_processed: {trend_snapshots}</li>
  <li>market_trend_enough_history: {trend_enough}</li>
  <li>fund_detail_available: {fund_available}</li>
  <li>watchlist_detail_count: {fund_count}</li>
</ul>
<p>当前系统可继续运行，dashboard 可继续查看，research loop 可继续积累证据。</p>
<p>insufficient_history 只影响主评分/主风险接入判断，不表示系统级失败。</p>
<p><a href="market.html">Market Intelligence 市场观察页</a></p>
<p><a href="funds.html">Watchlist Fund Details 自选基金详情页</a></p>
""".format(
        runs=len(summaries),
        status=html.escape(str(latest.get("status", "unknown"))),
        quality=html.escape(str(latest.get("data_quality_grade", "unknown"))),
        applied=html.escape(str((latest.get("experiment_scoring") or {}).get("applied_signal_count", 0))),
        research_ready=research_ready,
        dashboard_ready=dashboard_ready,
        market_available=str(bool(market_report)).lower(),
        trend_available=str(bool(market_trend)).lower(),
        trend_snapshots=html.escape(str(market_trend.get("snapshots_processed", 0))),
        trend_enough=html.escape(str(market_trend.get("enough_market_history", False))),
        fund_available=str(bool(fund_details)).lower(),
        fund_count=html.escape(str(fund_details.get("detail_count", 0))),
    )


def _runs_body(context: dict[str, Any]) -> str:
    rows = []
    for summary in context["summaries"]:
        steps = ", ".join(
            f"{step.get('step_name')}={step.get('status')}"
            for step in summary.get("steps") or []
        )
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html.escape(str(summary.get("as_of"))),
                html.escape(str(summary.get("status"))),
                html.escape(", ".join(summary.get("missing_artifacts") or [])),
                html.escape(steps),
            )
        )
    return "<h1>Runs</h1><table><tr><th>Date</th><th>Status</th><th>Missing artifacts</th><th>Steps</th></tr>{}</table>".format(
        "".join(rows)
    )


def _signals_body(context: dict[str, Any]) -> str:
    rows = []
    reasons: dict[str, int] = {}
    for summary in context["summaries"]:
        signals = summary.get("signal_candidates") or {}
        experiment = summary.get("experiment_scoring") or {}
        for reason, count in (experiment.get("top_exclusion_reasons") or {}).items():
            reasons[reason] = reasons.get(reason, 0) + int(count or 0)
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html.escape(str(summary.get("as_of"))),
                signals.get("eligible_count", 0),
                signals.get("excluded_count", 0),
                signals.get("display_only_count", 0),
                experiment.get("applied_signal_count", 0),
            )
        )
    reason_items = "".join(f"<li>{html.escape(str(k))}: {v}</li>" for k, v in sorted(reasons.items()))
    return "<h1>Signals</h1><table><tr><th>Date</th><th>Eligible</th><th>Excluded</th><th>Display-only</th><th>Applied</th></tr>{}</table><h2>Recurring blockers</h2><ul>{}</ul>".format(
        "".join(rows), reason_items
    )


def _review_body(context: dict[str, Any]) -> str:
    state = context["state_summary"]
    queue = context["queue_summary"]
    rows = []
    for item in context["review_items"]:
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html.escape(str(item.get("review_id"))),
                html.escape(str(item.get("signal_id"))),
                html.escape(str(item.get("status"))),
                html.escape(str(item.get("note", ""))),
            )
        )
    return """
<h1>Review</h1>
<p>manual_queue_total: {queue_total}</p>
<p>manual_review_state: approved={approved} rejected={rejected} needs_more_data={needs}</p>
<table><tr><th>Review ID</th><th>Signal</th><th>Status</th><th>Note</th></tr>{rows}</table>
""".format(
        queue_total=queue.get("total_review_items", 0),
        approved=state.get("approved_count", 0),
        rejected=state.get("rejected_count", 0),
        needs=state.get("needs_more_data_count", 0),
        rows="".join(rows),
    )


def _data_quality_body(context: dict[str, Any]) -> str:
    rows = []
    for summary in context["summaries"]:
        source = summary.get("data_source") or {}
        warnings = summary.get("provider_warnings") or {}
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html.escape(str(summary.get("as_of"))),
                html.escape(str(summary.get("data_quality_grade"))),
                html.escape(str(source.get("provider_warning_count", warnings.get("total", 0)))),
            )
        )
    return "<h1>Data Quality</h1><table><tr><th>Date</th><th>Grade</th><th>Provider warnings</th></tr>{}</table>".format(
        "".join(rows)
    )


def _market_body(context: dict[str, Any]) -> str:
    report = context.get("market_report") or {}
    trend = context.get("market_trend") or {}
    if not report:
        return """
<h1>Market Intelligence</h1>
<p>Market Intelligence 尚未运行。</p>
<h2>Market Trend Summary</h2>
<p>Market Trend 尚未运行。</p>
<p>运行后将展示全市场基金/ETF 数量、主题排行榜、热门主题候选和数据质量摘要。</p>
"""
    hot_rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            html.escape(str(item.get("theme"))),
            html.escape(str(item.get("sample_size"))),
            html.escape(str(item.get("avg_return_1m"))),
        )
        for item in report.get("hot_theme_candidates") or []
    )
    insufficient_rows = "".join(
        "<tr><td>{}</td><td>{}</td></tr>".format(
            html.escape(str(item.get("theme"))),
            html.escape(str(item.get("sample_size"))),
        )
        for item in report.get("insufficient_sample_themes") or []
    )
    warnings = "".join(f"<li>{html.escape(str(item))}</li>" for item in report.get("warnings") or [])
    data_quality = report.get("data_quality_summary") or {}
    trend_html = _market_trend_section(trend)
    return """
<h1>Market Intelligence</h1>
<ul>
  <li>as_of: {as_of}</li>
  <li>source: {source}</li>
  <li>total_funds: {funds}</li>
  <li>total_etfs: {etfs}</li>
  <li>theme_count: {themes}</li>
  <li>data_quality: {quality}</li>
  <li>latest_market_report_path: {path}</li>
  <li>not_production_model=true</li>
</ul>
<p>市场观察页只展示候选主题和数据质量，不输出买卖建议，不接入主评分/主风险。</p>
<h2>Hot Theme Candidates</h2>
<table><tr><th>Theme</th><th>Sample Size</th><th>Avg Return 1M</th></tr>{hot_rows}</table>
<h2>Insufficient Sample Themes</h2>
<table><tr><th>Theme</th><th>Sample Size</th></tr>{insufficient_rows}</table>
<h2>Warnings</h2>
<ul>{warnings}</ul>
{trend_html}
""".format(
        as_of=html.escape(str(report.get("as_of"))),
        source=html.escape(str(report.get("source"))),
        funds=html.escape(str(report.get("total_funds"))),
        etfs=html.escape(str(report.get("total_etfs"))),
        themes=html.escape(str(len(report.get("themes") or []))),
        quality=html.escape(str(data_quality.get("grade", "unknown"))),
        path=html.escape(str(report.get("_path", ""))),
        hot_rows=hot_rows,
        insufficient_rows=insufficient_rows,
        warnings=warnings or "<li>none</li>",
        trend_html=trend_html,
    )


def _market_trend_section(trend: dict[str, Any]) -> str:
    if not trend:
        return """
<h2>Market Trend Summary</h2>
<p>Market Trend 尚未运行。</p>
"""
    persistent = _trend_list(trend.get("persistent_hot_themes") or [])
    new_hot = _trend_list(trend.get("new_hot_themes") or [])
    rising = _trend_list(trend.get("rising_themes") or [])
    falling = _trend_list(trend.get("falling_themes") or [])
    quality_rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            html.escape(str(item.get("as_of"))),
            html.escape(str(item.get("data_quality_grade"))),
            html.escape(str(item.get("insufficient_sample_theme_count", 0))),
            html.escape(str(item.get("warning_count", 0))),
        )
        for item in trend.get("data_quality_trend") or []
    )
    warnings = "".join(f"<li>{html.escape(str(item))}</li>" for item in trend.get("warnings") or [])
    insufficient = ""
    if not trend.get("enough_market_history", False):
        insufficient = "<p>趋势样本不足，但 Market Intelligence 可继续运行。</p>"
    return """
<h2>Market Trend Summary</h2>
<ul>
  <li>snapshots_processed: {snapshots}</li>
  <li>minimum_required_snapshots: {minimum}</li>
  <li>enough_market_history: {enough}</li>
  <li>latest_as_of: {latest}</li>
</ul>
{insufficient}
<h3>Persistent Hot Themes</h3><ul>{persistent}</ul>
<h3>New Hot Themes</h3><ul>{new_hot}</ul>
<h3>Rising Themes</h3><ul>{rising}</ul>
<h3>Falling Themes</h3><ul>{falling}</ul>
<h3>Data Quality Trend</h3>
<table><tr><th>Date</th><th>Grade</th><th>Insufficient Themes</th><th>Warnings</th></tr>{quality_rows}</table>
<h3>Trend Warnings</h3><ul>{warnings}</ul>
""".format(
        snapshots=html.escape(str(trend.get("snapshots_processed", 0))),
        minimum=html.escape(str(trend.get("minimum_required_snapshots", 0))),
        enough=html.escape(str(trend.get("enough_market_history", False))),
        latest=html.escape(str(trend.get("latest_as_of"))),
        insufficient=insufficient,
        persistent=persistent,
        new_hot=new_hot,
        rising=rising,
        falling=falling,
        quality_rows=quality_rows or "<tr><td colspan=\"4\">none</td></tr>",
        warnings=warnings or "<li>none</li>",
    )


def _trend_list(items: list[dict[str, Any]]) -> str:
    if not items:
        return "<li>none</li>"
    return "".join(
        "<li>{theme}: latest_rank={rank}, rank_change={change}, hot_days={hot_days}</li>".format(
            theme=html.escape(str(item.get("theme"))),
            rank=html.escape(str(item.get("latest_rank"))),
            change=html.escape(str(item.get("rank_change"))),
            hot_days=html.escape(str(item.get("hot_days", 0))),
        )
        for item in items
    )


def _funds_body(context: dict[str, Any]) -> str:
    payload = context.get("fund_details") or {}
    if not payload:
        return """
<h1>Watchlist Fund Details</h1>
<p>Fund Detail 尚未运行。</p>
<p>运行 watchlist-detail 后将展示自选基金详情、主题归类、收益窗口、数据质量和 signal/review 状态。</p>
"""
    rows = []
    for item in payload.get("fund_details") or []:
        returns = item.get("return_windows") or {}
        signal = item.get("signal_context") or {}
        coverage = item.get("data_coverage") or {}
        peer = item.get("peer_comparison") or {}
        missing = item.get("missing_fields") or []
        code = str(item.get("code"))
        rows.append(
            "<tr><td><a href=\"funds/{code}.html\">{code}</a></td><td>{name}</td><td>{fund_type}</td><td>{theme}</td><td>{coverage_status}</td><td>{coverage_ratio}</td><td>{peer_sample}</td><td>{peer_status}</td><td>{quality}</td><td>{r1m}</td><td>{r3m}</td><td>{r6m}</td><td>{r1y}</td><td>{signal}</td><td>{review}</td><td>{missing}</td><td>{path}</td></tr>".format(
                code=html.escape(code),
                name=html.escape(str(item.get("name") or "")),
                fund_type=html.escape(str(item.get("fund_type") or "")),
                theme=html.escape(str(item.get("primary_theme") or "")),
                coverage_status=html.escape(str(coverage.get("status", "unknown"))),
                coverage_ratio=html.escape(str(coverage.get("coverage_ratio", ""))),
                peer_sample=html.escape(str(peer.get("peer_sample_size", 0))),
                peer_status=html.escape(str(peer.get("sample_status", "unknown"))),
                quality=html.escape(str(item.get("data_quality_grade") or "")),
                r1m=html.escape(_return_value(returns, "1m")),
                r3m=html.escape(_return_value(returns, "3m")),
                r6m=html.escape(_return_value(returns, "6m")),
                r1y=html.escape(_return_value(returns, "1y")),
                signal=html.escape(str(signal.get("signal_status", "none"))),
                review=html.escape(str(signal.get("manual_review_status", "none"))),
                missing=html.escape(str(len(missing))),
                path=html.escape(str(item.get("latest_detail_json_path") or f"fund_details/fund_detail_{code}.json")),
            )
        )
    return """
<h1>Watchlist Fund Details</h1>
<ul>
  <li>as_of: {as_of}</li>
  <li>detail_count: {count}</li>
  <li>missing_count: {missing}</li>
  <li>warning_count: {warnings}</li>
  <li>average_coverage_ratio: {coverage}</li>
  <li>unknown_theme_count: {unknown_theme}</li>
  <li>peer_insufficient_count: {peer_insufficient}</li>
  <li>not_production_model=true</li>
</ul>
<p>Fund Detail 是观察页，不接主评分/主风险，不构成投资建议。</p>
<table><tr><th>Code</th><th>Name</th><th>Type</th><th>Primary Theme</th><th>Coverage</th><th>Coverage Ratio</th><th>Peer Sample</th><th>Peer Status</th><th>Quality</th><th>1M</th><th>3M</th><th>6M</th><th>1Y</th><th>Signal</th><th>Manual Review</th><th>Missing</th><th>Detail JSON</th></tr>{rows}</table>
""".format(
        as_of=html.escape(str(payload.get("as_of") or "")),
        count=html.escape(str(payload.get("detail_count", 0))),
        missing=html.escape(str(payload.get("missing_count", 0))),
        warnings=html.escape(str(payload.get("warning_count", 0))),
        coverage=html.escape(str((payload.get("coverage_summary") or {}).get("average_coverage_ratio", 0))),
        unknown_theme=html.escape(str((payload.get("coverage_summary") or {}).get("unknown_theme_count", 0))),
        peer_insufficient=html.escape(str((payload.get("coverage_summary") or {}).get("peer_insufficient_count", 0))),
        rows="".join(rows),
    )


def _write_fund_detail_pages(output: Path, payload: dict[str, Any]) -> None:
    details = payload.get("fund_details") or []
    if not details:
        return
    details_dir = output / "funds"
    details_dir.mkdir(parents=True, exist_ok=True)
    for item in details:
        code = str(item.get("code") or "")
        if not code:
            continue
        body = _single_fund_detail_body(item)
        (details_dir / f"{code}.html").write_text(
            "\n".join(
                [
                    "<!doctype html>",
                    f"<html><head><meta charset=\"utf-8\"><title>{html.escape(code)}</title></head>",
                    "<body>",
                    "<nav><a href=\"../index.html\">Index</a> <a href=\"../funds.html\">Funds</a> <a href=\"../market.html\">Market</a></nav>",
                    "<p><strong>not_production_model=true</strong></p>",
                    body,
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )


def _single_fund_detail_body(item: dict[str, Any]) -> str:
    coverage = item.get("data_coverage") or {}
    peer = item.get("peer_comparison") or {}
    rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            html.escape(str(window)),
            html.escape(str((summary or {}).get("total_return"))),
            html.escape(str((summary or {}).get("data_quality_grade"))),
        )
        for window, summary in (item.get("return_windows") or {}).items()
    )
    missing = "".join(f"<li>{html.escape(str(value))}</li>" for value in item.get("missing_fields") or [])
    warnings = "".join(f"<li>{html.escape(str(value))}</li>" for value in item.get("data_quality_warnings") or [])
    coverage_rows = "".join(
        f"<li>{html.escape(str(value))}</li>" for value in coverage.get("available_fields") or []
    )
    peer_warnings = "".join(f"<li>{html.escape(str(value))}</li>" for value in peer.get("warnings") or [])
    return """
<h1>{code} {name}</h1>
<ul>
  <li>fund_type: {fund_type}</li>
  <li>source: {source}</li>
  <li>as_of: {as_of}</li>
  <li>primary_theme: {theme}</li>
  <li>unknown_reason: {unknown_reason}</li>
  <li>data_quality_grade: {quality}</li>
</ul>
<p>仅用于观察，不接主评分/主风险，不构成投资建议。</p>
<h2>Data Coverage</h2>
<ul>
  <li>status: {coverage_status}</li>
  <li>coverage_ratio: {coverage_ratio}</li>
  <li>return_window_count: {return_window_count}</li>
  <li>available_fields: <ul>{coverage_rows}</ul></li>
</ul>
<h2>Peer Comparison</h2>
<ul>
  <li>primary_theme: {peer_theme}</li>
  <li>peer_sample_size: {peer_sample}</li>
  <li>sample_status: {peer_status}</li>
  <li>rank_by_1m_return: {peer_rank_return}</li>
  <li>rank_by_scale: {peer_rank_scale}</li>
  <li>warnings: <ul>{peer_warnings}</ul></li>
</ul>
<h2>Return Windows</h2>
<table><tr><th>Window</th><th>Total Return</th><th>Quality</th></tr>{rows}</table>
<h2>Missing Fields</h2><ul>{missing}</ul>
<h2>Warnings</h2><ul>{warnings}</ul>
""".format(
        code=html.escape(str(item.get("code") or "")),
        name=html.escape(str(item.get("name") or "")),
        fund_type=html.escape(str(item.get("fund_type") or "")),
        source=html.escape(str(item.get("source") or "")),
        as_of=html.escape(str(item.get("as_of") or "")),
        theme=html.escape(str(item.get("primary_theme") or "")),
        unknown_reason=html.escape(str(item.get("unknown_reason") or "")),
        quality=html.escape(str(item.get("data_quality_grade") or "")),
        coverage_status=html.escape(str(coverage.get("status", "unknown"))),
        coverage_ratio=html.escape(str(coverage.get("coverage_ratio", ""))),
        return_window_count=html.escape(str(coverage.get("return_window_count", 0))),
        coverage_rows=coverage_rows or "<li>none</li>",
        peer_theme=html.escape(str(peer.get("primary_theme", "unknown"))),
        peer_sample=html.escape(str(peer.get("peer_sample_size", 0))),
        peer_status=html.escape(str(peer.get("sample_status", "unknown"))),
        peer_rank_return=html.escape(str(peer.get("rank_by_1m_return"))),
        peer_rank_scale=html.escape(str(peer.get("rank_by_scale"))),
        peer_warnings=peer_warnings or "<li>none</li>",
        rows=rows,
        missing=missing or "<li>none</li>",
        warnings=warnings or "<li>none</li>",
    )


def _return_value(returns: dict[str, Any], window: str) -> str:
    item = returns.get(window) or {}
    value = item.get("total_return") if isinstance(item, dict) else None
    return "--" if value is None else str(value)


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


def _latest_market_report(run_dirs: list[Path], output_dir: Path) -> dict[str, Any]:
    candidates = [output_dir.parent / "market" / "market_intelligence_report.json"]
    candidates.extend(path / "market_intelligence_report.json" for path in reversed(run_dirs))
    for path in candidates:
        payload = _load_json(path)
        if payload:
            payload["_path"] = str(path)
            return payload
    return {}


def _latest_market_trend(output_dir: Path) -> dict[str, Any]:
    path = output_dir.parent / "market" / "market_trend_report.json"
    payload = _load_json(path)
    if payload:
        payload["_path"] = str(path)
    return payload


def _latest_fund_details(output_dir: Path) -> dict[str, Any]:
    path = output_dir.parent / "fund_details" / "watchlist_fund_details.json"
    payload = _load_json(path)
    if payload:
        payload["_path"] = str(path)
        for item in payload.get("fund_details") or []:
            code = str(item.get("code") or "")
            item["latest_detail_json_path"] = str(output_dir.parent / "fund_details" / f"fund_detail_{code}.json")
    return payload
