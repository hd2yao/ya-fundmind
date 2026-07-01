from __future__ import annotations

import html
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .research_loop import aggregate_manual_review_queues
from .review_state import list_review_state, summarize_review_state


PAGES = ("index.html", "runs.html", "signals.html", "review.html", "data_quality.html", "market.html")


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
    }
    _write_page(output / "index.html", "Evidence Dashboard", _index_body(context))
    _write_page(output / "runs.html", "Runs", _runs_body(context))
    _write_page(output / "signals.html", "Signals", _signals_body(context))
    _write_page(output / "review.html", "Manual Review", _review_body(context))
    _write_page(output / "data_quality.html", "Data Quality", _data_quality_body(context))
    _write_page(output / "market.html", "Market Intelligence", _market_body(context))
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
                "<nav><a href=\"index.html\">Index</a> <a href=\"runs.html\">Runs</a> <a href=\"signals.html\">Signals</a> <a href=\"review.html\">Review</a> <a href=\"data_quality.html\">Data Quality</a> <a href=\"market.html\">Market</a></nav>",
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
</ul>
<p>当前系统可继续运行，dashboard 可继续查看，research loop 可继续积累证据。</p>
<p>insufficient_history 只影响主评分/主风险接入判断，不表示系统级失败。</p>
<p><a href="market.html">Market Intelligence 市场观察页</a></p>
""".format(
        runs=len(summaries),
        status=html.escape(str(latest.get("status", "unknown"))),
        quality=html.escape(str(latest.get("data_quality_grade", "unknown"))),
        applied=html.escape(str((latest.get("experiment_scoring") or {}).get("applied_signal_count", 0))),
        research_ready=research_ready,
        dashboard_ready=dashboard_ready,
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
    if not report:
        return """
<h1>Market Intelligence</h1>
<p>Market Intelligence 尚未运行。</p>
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
    )


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
