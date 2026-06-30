from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from .agents import ResearchResult
from .snapshot import _provider_health_to_dict


DISCLAIMER = "本报告仅用于研究辅助，不构成投资建议，不包含任何自动交易指令。"
SCHEMA_VERSION = "1.0"
GENERATOR = "fund_agent"


def render_markdown(result: ResearchResult) -> str:
    lines: list[str] = [
        "# YA FundMind 基金智研系统日报",
        "",
        f"> {DISCLAIMER}",
        "",
        f"- 版本日期: {result.as_of or '未指定'}",
        f"- 候选数量: {len(result.ranked_candidates)}",
        "",
        "## Agent 运行摘要",
        "",
    ]
    for trace in result.traces:
        lines.append(f"- **{trace.agent_name}**: {trace.summary}")

    lines.extend(
        [
            "",
            "## 今日数据质量摘要",
            "",
            f"- 数据质量等级: {result.data_quality_grade}",
        ]
    )
    provider_count = len(result.provider_health)
    fallback_count = sum(1 for health in result.provider_health if health.fallback_used)
    stale_count = sum(
        1 for valuation in result.valuations.values() if valuation.fund.metadata.get("stale")
    )
    critical_count = sum(
        1
        for health in result.provider_health
        for warning in health.warnings
        if warning.severity == "critical"
    )
    warning_count = sum(
        1
        for health in result.provider_health
        for warning in health.warnings
        if warning.severity == "warning"
    )
    lines.append(f"- Provider 数量: {provider_count}")
    lines.append(f"- Fallback 使用: {fallback_count}")
    lines.append(f"- Stale cache 记录: {stale_count}")
    lines.append(f"- Critical warnings: {critical_count}")
    lines.append(f"- Warning 级别 warnings: {warning_count}")

    if result.provider_health:
        lines.extend(
            [
                "",
                "## 数据源健康状态",
                "",
                "| Provider | Version | Duration(ms) | Live Rows | Mapped | Skipped | Cache Writes | Fallback | Watchlist |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
            ]
        )
        for health in result.provider_health:
            fallback = "是" if health.fallback_used else "否"
            version = health.provider_version or "--"
            watchlist = (
                f"{health.watchlist_matched_count}/{health.watchlist_requested_count}"
                if health.watchlist_requested_count
                else "--"
            )
            lines.append(
                f"| {health.provider} | {version} | {health.duration_ms} | {health.live_row_count} | {health.mapped_row_count} | {health.skipped_row_count} | {health.cache_write_count} | {fallback} | {watchlist} |"
            )
            if health.fallback_used:
                lines.append(
                    f"- fallback: source={health.fallback_source or '--'} reason={health.fallback_reason or '--'}"
                )
            if health.watchlist_missing_codes:
                lines.append(f"- watchlist_missing: {', '.join(health.watchlist_missing_codes)}")
        warnings = [
            (health.provider, warning)
            for health in result.provider_health
            for warning in health.warnings
        ]
        lines.extend(["", "### Provider Warnings", ""])
        if warnings:
            grouped = defaultdict(list)
            for provider, warning in warnings:
                grouped[warning.severity].append((provider, warning))
            for severity, title in (
                ("critical", "Critical"),
                ("warning", "Warning"),
                ("info", "Info"),
            ):
                lines.extend(["", f"### {title}", ""])
                items = grouped.get(severity, [])
                if not items:
                    lines.append("- 无")
                    continue
                for provider, warning in items:
                    lines.append(
                        f"- `{provider}:{warning.code}`: {warning.message}"
                    )
        else:
            lines.append("- 暂无 fallback warning 或 provider warning。")

    lines.extend(
        [
            "",
            "## 数据来源与新鲜度",
            "",
            "| 代码 | 名称 | 来源 | as_of | updated_at | expires_at | stale |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for valuation in sorted(result.valuations.values(), key=lambda item: item.fund.code):
        fund = valuation.fund
        metadata = fund.metadata
        source = fund.source
        as_of = metadata.get("as_of") or metadata.get("cache_as_of") or result.as_of or "--"
        updated_at = metadata.get("updated_at", "--")
        expires_at = metadata.get("expires_at", "--")
        stale = "是" if metadata.get("stale") else "否"
        lines.append(
            f"| {fund.code} | {fund.name} | {source} | {as_of} | {updated_at} | {expires_at} | {stale} |"
        )

    lines.extend(
        [
            "",
            "## 研究优先级",
            "",
            "| 排名 | 代码 | 名称 | 类型 | 分数 | 证据 | 估值方式 | 置信度 |",
            "| --- | --- | --- | --- | ---: | --- | --- | --- |",
        ]
    )
    for idx, candidate in enumerate(result.ranked_candidates, start=1):
        valuation = result.valuations.get(candidate.fund.code)
        lines.append(
            "| {rank} | {code} | {name} | {category} | {score:.2f} | {evidence} | {method} | {confidence} |".format(
                rank=idx,
                code=candidate.fund.code,
                name=candidate.fund.name,
                category=candidate.fund.category,
                score=candidate.total_score,
                evidence=candidate.evidence_label,
                method=valuation.method if valuation else "missing",
                confidence=valuation.confidence if valuation else "Needs checking",
            )
        )

    lines.extend(["", "## 估值方式与数据缺口", ""])
    for valuation in result.valuations.values():
        notes = list(valuation.notes)
        if valuation.fund.metadata.get("stale"):
            expires_at = valuation.fund.metadata.get("expires_at", "unknown")
            notes.append(f"stale data: cache expired at {expires_at}")
        note = "；".join(notes) if notes else "无"
        value = "--" if valuation.estimated_value is None else f"{valuation.estimated_value:.4f}"
        lines.append(
            f"- {valuation.fund.code} {valuation.fund.name}: {valuation.method}, 估值 {value}, 置信度 {valuation.confidence}。{note}"
        )

    if result.portfolio:
        lines.extend(
            [
                "",
                "## 组合概览",
                "",
                f"- 当前市值: {result.portfolio.total_value:.2f}",
                f"- 成本合计: {result.portfolio.total_cost:.2f}",
                f"- 浮动收益率: {result.portfolio.total_unrealized_return_pct:.2f}%",
                "",
                "| 代码 | 名称 | 当前市值 | 权重 | 浮动收益 | 目标偏离 |",
                "| --- | --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for position in result.portfolio.positions:
            drift = "--" if position.target_drift is None else f"{position.target_drift:.2%}"
            lines.append(
                f"| {position.holding.code} | {position.holding.name} | {position.current_value:.2f} | {position.weight:.2%} | {position.unrealized_return_pct:.2f}% | {drift} |"
            )

        lines.extend(["", "## 风险提示", ""])
        if result.portfolio.risk_issues:
            for issue in result.portfolio.risk_issues:
                lines.append(f"- **{issue.severity}** `{issue.code}`: {issue.message}")
        else:
            lines.append("- 暂无组合层面的集中风险提示；仍需人工核对数据源。")

    if result.snapshot_delta:
        lines.extend(["", "## 历史快照对比", ""])
        previous_as_of = result.snapshot_delta.get("previous_as_of", "上一期")
        lines.append(f"- 对比基准: {previous_as_of}")
        score_changes = result.snapshot_delta.get("score_changes", [])
        if score_changes:
            lines.append("- 评分变化:")
            for item in score_changes[:5]:
                lines.append(
                    f"  - {item['code']} {item.get('name', '')}: {item['delta']:+.2f}"
                )
        valuation_changes = result.snapshot_delta.get("valuation_changes", [])
        if valuation_changes:
            lines.append("- 估值变化:")
            for item in valuation_changes[:5]:
                delta = item.get("value_delta")
                delta_text = "--" if delta is None else f"{delta:+.4f}"
                lines.append(f"  - {item['code']}: {delta_text}")
        risk_changes = result.snapshot_delta.get("risk_changes", {})
        added = risk_changes.get("added", [])
        resolved = risk_changes.get("resolved", [])
        lines.append(f"- 风险变化: 新增 {len(added)} 条，解除 {len(resolved)} 条。")
        holding_delta = result.snapshot_delta.get("holding_risk_changes", {})
        if holding_delta:
            lines.append(
                "- 持仓风险变化: 风险数量 {:+d}，市值变化 {}。".format(
                    int(holding_delta.get("risk_count_delta", 0)),
                    holding_delta.get("total_value_delta", "--"),
                )
            )
        data_quality_delta = result.snapshot_delta.get("data_quality_grade_delta")
        provider_delta = result.snapshot_delta.get("provider_health_delta", {})
        if data_quality_delta or provider_delta:
            lines.extend(["", "## 数据质量变化", ""])
            if data_quality_delta:
                lines.append(
                    "- data_quality_grade: {} -> {}".format(
                        data_quality_delta.get("previous", "unknown"),
                        data_quality_delta.get("current", "unknown"),
                    )
                )
            for provider, item in provider_delta.items():
                lines.append(
                    "- {provider}: live rows {live:+d}, skipped rows {skipped:+d}, warnings {warnings:+d}, fallback_changed {fallback}".format(
                        provider=provider,
                        live=int(item.get("provider_live_rows_delta", 0)),
                        skipped=int(item.get("provider_skipped_rows_delta", 0)),
                        warnings=int(item.get("warning_count_delta", 0)),
                        fallback=item.get("fallback_changed", False),
                    )
                )

    if result.fund_details or result.nav_history_summary:
        lines.extend(["", "## 基金详情补充数据", ""])
        if result.fund_details:
            lines.extend(
                [
                    "| 代码 | 名称 | 基金公司 | 基金经理 | 成立日期 | 规模 | 评级 | 来源 |",
                    "| --- | --- | --- | --- | --- | ---: | --- | --- |",
                ]
            )
            for detail in result.fund_details:
                scale = "--" if detail.scale is None else f"{detail.scale:.4f}"
                lines.append(
                    f"| {detail.code} | {detail.name} | {detail.fund_company or '--'} | {detail.fund_manager or '--'} | {detail.inception_date or '--'} | {scale} | {detail.rating or '--'} | {detail.source} |"
                )
        if result.nav_history_summary:
            lines.extend(
                [
                    "",
                    "### 历史净值摘要",
                    "",
                    "| 代码 | 样本数 | 起始日期 | 截止日期 | 最新单位净值 | 总收益 | 最大回撤 | 波动率 | 数据质量 |",
                    "| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | --- |",
                ]
            )
            for code, summary in sorted(result.nav_history_summary.items()):
                lines.append(
                    "| {code} | {count} | {start} | {end} | {latest} | {total} | {drawdown} | {volatility} | {grade} |".format(
                        code=code,
                        count=summary.get("count", 0),
                        start=summary.get("start_date") or "--",
                        end=summary.get("end_date") or "--",
                        latest=_format_optional_number(summary.get("latest_unit_nav")),
                        total=_format_optional_number(summary.get("total_return")),
                        drawdown=_format_optional_number(summary.get("max_drawdown")),
                        volatility=_format_optional_number(summary.get("volatility")),
                        grade=summary.get("data_quality_grade", "unknown"),
                    )
                )

    lines.extend(
        [
            "",
            "## 下一步核对",
            "",
            "- 核对基金公告、基金合同、最新季报和持仓变化。",
            "- 对跨境/QDII 产品核对汇率、时区、申赎限制和折溢价。",
            "- 对短期涨幅过快的产品检查是否存在追高风险。",
        ]
    )
    return "\n".join(lines) + "\n"


def render_html(result: ResearchResult) -> str:
    provider_count = len(result.provider_health)
    fallback_count = sum(1 for health in result.provider_health if health.fallback_used)
    stale_count = sum(
        1 for valuation in result.valuations.values() if valuation.fund.metadata.get("stale")
    )
    critical_count = sum(
        1
        for health in result.provider_health
        for warning in health.warnings
        if warning.severity == "critical"
    )
    warning_count = sum(
        1
        for health in result.provider_health
        for warning in health.warnings
        if warning.severity == "warning"
    )
    live_rows = sum(health.live_row_count for health in result.provider_health)
    risk_count = len(result.portfolio.risk_issues) if result.portfolio else 0
    quality_class = _html_token(result.data_quality_grade)

    body = "\n".join(
        [
            '<div class="app-shell">',
            _render_side_nav(result),
            '<main class="report-main">',
            '<header class="hero">',
            '<div>',
            '<p class="eyebrow">YA FundMind Daily Research</p>',
            f"<h1>基金智研系统日报</h1>",
            f'<p class="disclaimer">{_html(DISCLAIMER)}</p>',
            "</div>",
            '<div class="hero-status">',
            f'<span class="status-pill status-{quality_class}">数据质量 {_html(result.data_quality_grade)}</span>',
            f'<span class="status-pill">as_of {_html(result.as_of or "未指定")}</span>',
            "</div>",
            "</header>",
            '<section class="metric-grid" aria-label="关键指标">',
            _metric_card("候选基金", str(len(result.ranked_candidates)), "研究优先级列表"),
            _metric_card("Live Rows", str(live_rows), "provider 实时映射行数"),
            _metric_card("Fallback", str(fallback_count), "本次 fallback 次数", "warn" if fallback_count else "ok"),
            _metric_card("风险提示", str(risk_count), "组合层风险条目", "danger" if risk_count else "ok"),
            _metric_card("Provider", str(provider_count), "数据源数量"),
            _metric_card("Stale Cache", str(stale_count), "过期缓存记录", "danger" if stale_count else "ok"),
            "</section>",
            _render_agent_section(result),
            _render_data_quality_section(
                result,
                provider_count=provider_count,
                fallback_count=fallback_count,
                stale_count=stale_count,
                critical_count=critical_count,
                warning_count=warning_count,
            ),
            _render_freshness_section(result),
            _render_research_priority_section(result),
            _render_valuation_section(result),
            _render_portfolio_section(result),
            _render_snapshot_section(result),
            _render_enrichment_section(result),
            _render_next_steps_section(),
            "</main>",
            "</div>",
        ]
    )
    return (
        "<!doctype html>\n"
        "<html lang=\"zh-CN\">\n"
        "<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>YA FundMind 基金智研系统日报</title>\n"
        f"<style>{_REPORT_CSS}</style>\n"
        "</head>\n"
        f"<body>{body}</body>\n"
        "</html>\n"
    )


def _render_side_nav(result: ResearchResult) -> str:
    items = [
        ("overview", "运行摘要"),
        ("data-quality", "数据质量"),
        ("freshness", "新鲜度"),
        ("research-priority", "研究优先级"),
        ("valuation", "估值"),
    ]
    if result.portfolio:
        items.append(("portfolio", "组合与风险"))
    if result.snapshot_delta:
        items.append(("snapshot-delta", "历史变化"))
    if result.fund_details or result.nav_history_summary:
        items.append(("enrichment", "补充数据"))
    items.append(("next-checks", "下一步"))
    links = "\n".join(
        f'<a href="#{anchor}">{_html(label)}</a>' for anchor, label in items
    )
    return (
        '<aside class="report-sidebar">'
        '<div class="brand">YA FundMind</div>'
        '<nav class="section-nav" aria-label="报告模块">'
        f"{links}"
        "</nav>"
        '<p class="sidebar-note">本页只展示研究辅助结果，不生成交易指令。</p>'
        "</aside>"
    )


def _render_agent_section(result: ResearchResult) -> str:
    items = "\n".join(
        '<li><span class="agent-name">{}</span><span>{}</span></li>'.format(
            _html(trace.agent_name),
            _html(trace.summary),
        )
        for trace in result.traces
    )
    return (
        '<section id="overview" class="report-section">'
        '<details class="report-panel" open>'
        "<summary>Agent 运行摘要</summary>"
        f'<ul class="agent-list">{items}</ul>'
        "</details>"
        "</section>"
    )


def _render_data_quality_section(
    result: ResearchResult,
    *,
    provider_count: int,
    fallback_count: int,
    stale_count: int,
    critical_count: int,
    warning_count: int,
) -> str:
    health_rows = []
    for health in result.provider_health:
        fallback = "是" if health.fallback_used else "否"
        version = health.provider_version or "--"
        watchlist = (
            f"{health.watchlist_matched_count}/{health.watchlist_requested_count}"
            if health.watchlist_requested_count
            else "--"
        )
        health_rows.append(
            [
                _html(health.provider),
                _html(version),
                str(health.duration_ms),
                str(health.live_row_count),
                str(health.mapped_row_count),
                str(health.skipped_row_count),
                str(health.cache_write_count),
                _html(fallback),
                _html(watchlist),
            ]
        )
    warnings = [
        (health.provider, warning)
        for health in result.provider_health
        for warning in health.warnings
    ]
    warning_html = _render_provider_warnings(warnings)
    health_table = _table(
        [
            "Provider",
            "Version",
            "Duration(ms)",
            "Live Rows",
            "Mapped",
            "Skipped",
            "Cache Writes",
            "Fallback",
            "Watchlist",
        ],
        health_rows,
    )
    return (
        '<section id="data-quality" class="report-section">'
        '<details class="report-panel" open>'
        "<summary>今日数据质量摘要</summary>"
        '<div class="mini-grid">'
        f'{_metric_card("数据质量", result.data_quality_grade, "整体报告置信状态", result.data_quality_grade)}'
        f'{_metric_card("Provider", str(provider_count), "数据源数量")}'
        f'{_metric_card("Fallback", str(fallback_count), "fallback 使用次数", "warn" if fallback_count else "ok")}'
        f'{_metric_card("Stale", str(stale_count), "过期缓存记录", "danger" if stale_count else "ok")}'
        f'{_metric_card("Critical", str(critical_count), "critical warnings", "danger" if critical_count else "ok")}'
        f'{_metric_card("Warning", str(warning_count), "warning 级别 warnings", "warn" if warning_count else "ok")}'
        "</div>"
        '<h3>数据源健康状态</h3>'
        f"{health_table}"
        '<h3>Provider Warnings</h3>'
        f"{warning_html}"
        "</details>"
        "</section>"
    )


def _render_provider_warnings(warnings) -> str:
    if not warnings:
        return '<p class="empty-state">暂无 fallback warning 或 provider warning。</p>'
    grouped = defaultdict(list)
    for provider, warning in warnings:
        grouped[warning.severity].append((provider, warning))
    sections = []
    for severity, title in (
        ("critical", "Critical"),
        ("warning", "Warning"),
        ("info", "Info"),
    ):
        items = grouped.get(severity, [])
        if not items:
            continue
        rows = "\n".join(
            '<li><span class="severity severity-{sev}">{title}</span>'
            '<code>{provider}:{code}</code><span>{message}</span></li>'.format(
                sev=_html_token(severity),
                title=_html(title),
                provider=_html(provider),
                code=_html(warning.code),
                message=_html(warning.message),
            )
            for provider, warning in items
        )
        sections.append(f'<ul class="warning-list">{rows}</ul>')
    return "\n".join(sections)


def _render_freshness_section(result: ResearchResult) -> str:
    rows = []
    for valuation in sorted(result.valuations.values(), key=lambda item: item.fund.code):
        fund = valuation.fund
        metadata = fund.metadata
        as_of = metadata.get("as_of") or metadata.get("cache_as_of") or result.as_of or "--"
        updated_at = metadata.get("updated_at", "--")
        expires_at = metadata.get("expires_at", "--")
        stale = "是" if metadata.get("stale") else "否"
        rows.append(
            [
                f'<a href="#fund-{_html_attr(fund.code)}">{_html(fund.code)}</a>',
                _html(fund.name),
                _html(fund.source),
                _html(as_of),
                _html(updated_at),
                _html(expires_at),
                f'<span class="status-pill status-{"warn" if metadata.get("stale") else "ok"}">{_html(stale)}</span>',
            ]
        )
    return (
        '<section id="freshness" class="report-section">'
        '<details class="report-panel" open>'
        "<summary>数据来源与新鲜度</summary>"
        f"{_table(['代码', '名称', '来源', 'as_of', 'updated_at', 'expires_at', 'stale'], rows)}"
        "</details>"
        "</section>"
    )


def _render_research_priority_section(result: ResearchResult) -> str:
    rows = []
    for idx, candidate in enumerate(result.ranked_candidates, start=1):
        fund = candidate.fund
        valuation = result.valuations.get(fund.code)
        confidence = valuation.confidence if valuation else "Needs checking"
        rows.append(
            _HtmlRow(
                [
                    str(idx),
                    f'<a class="fund-link" href="#fund-{_html_attr(fund.code)}">{_html(fund.code)}</a>',
                    _html(fund.name),
                    _html(fund.category),
                    f'<span class="score">{candidate.total_score:.2f}</span>',
                    f'<span class="status-pill status-{_html_token(candidate.evidence_label)}">{_html(candidate.evidence_label)}</span>',
                    _html(valuation.method if valuation else "missing"),
                    f'<span class="status-pill status-{_html_token(confidence)}">{_html(confidence)}</span>',
                ],
                row_attrs=f'id="fund-{_html_attr(fund.code)}" data-code="{_html_attr(fund.code)}"',
            )
        )
    return (
        '<section id="research-priority" class="report-section">'
        '<details class="report-panel" open>'
        "<summary>研究优先级</summary>"
        f"{_table(['排名', '代码', '名称', '类型', '分数', '证据', '估值方式', '置信度'], rows)}"
        "</details>"
        "</section>"
    )


def _render_valuation_section(result: ResearchResult) -> str:
    cards = []
    for valuation in result.valuations.values():
        fund = valuation.fund
        notes = list(valuation.notes)
        if fund.metadata.get("stale"):
            expires_at = fund.metadata.get("expires_at", "unknown")
            notes.append(f"stale data: cache expired at {expires_at}")
        note_html = "".join(f"<li>{_html(note)}</li>" for note in notes) or "<li>无</li>"
        value = "--" if valuation.estimated_value is None else f"{valuation.estimated_value:.4f}"
        cards.append(
            '<article class="valuation-card">'
            f'<div><a href="#fund-{_html_attr(fund.code)}" class="fund-link">{_html(fund.code)}</a>'
            f'<h3>{_html(fund.name)}</h3></div>'
            f'<div class="valuation-value">{_html(value)}</div>'
            '<dl class="definition-grid">'
            f'<dt>估值方式</dt><dd>{_html(valuation.method)}</dd>'
            f'<dt>置信度</dt><dd><span class="status-pill status-{_html_token(valuation.confidence)}">{_html(valuation.confidence)}</span></dd>'
            "</dl>"
            f'<ul class="note-list">{note_html}</ul>'
            "</article>"
        )
    return (
        '<section id="valuation" class="report-section">'
        '<details class="report-panel" open>'
        "<summary>估值方式与数据缺口</summary>"
        f'<div class="valuation-grid">{"".join(cards)}</div>'
        "</details>"
        "</section>"
    )


def _render_portfolio_section(result: ResearchResult) -> str:
    if result.portfolio is None:
        return ""
    positions = []
    for position in result.portfolio.positions:
        drift = "--" if position.target_drift is None else f"{position.target_drift:.2%}"
        positions.append(
            [
                f'<a href="#fund-{_html_attr(position.holding.code)}">{_html(position.holding.code)}</a>',
                _html(position.holding.name),
                f"{position.current_value:.2f}",
                f"{position.weight:.2%}",
                f"{position.unrealized_return_pct:.2f}%",
                _html(drift),
            ]
        )
    risks = []
    for issue in result.portfolio.risk_issues:
        severity = issue.severity.lower()
        risks.append(
            '<li><span class="severity severity-{severity}">{label}</span>'
            '<code>{code}</code><span>{message}</span></li>'.format(
                severity=_html_token(severity),
                label=_html(issue.severity),
                code=_html(issue.code),
                message=_html(issue.message),
            )
        )
    risk_html = (
        f'<ul class="risk-list">{"".join(risks)}</ul>'
        if risks
        else '<p class="empty-state">暂无组合层面的集中风险提示；仍需人工核对数据源。</p>'
    )
    return (
        '<section id="portfolio" class="report-section">'
        '<details class="report-panel" open>'
        "<summary>组合概览与风险提示</summary>"
        '<div class="mini-grid">'
        f'{_metric_card("当前市值", f"{result.portfolio.total_value:.2f}", "组合估算市值")}'
        f'{_metric_card("成本合计", f"{result.portfolio.total_cost:.2f}", "本地持仓成本")}'
        f'{_metric_card("浮动收益率", f"{result.portfolio.total_unrealized_return_pct:.2f}%", "基于当前估值")}'
        f'{_metric_card("风险提示", str(len(result.portfolio.risk_issues)), "组合层检查项", "danger" if result.portfolio.risk_issues else "ok")}'
        "</div>"
        f"{_table(['代码', '名称', '当前市值', '权重', '浮动收益', '目标偏离'], positions)}"
        "<h3>风险提示</h3>"
        f"{risk_html}"
        "</details>"
        "</section>"
    )


def _render_snapshot_section(result: ResearchResult) -> str:
    if not result.snapshot_delta:
        return ""
    delta = result.snapshot_delta
    score_items = "".join(
        "<li>{code} {name}: {delta:+.2f}</li>".format(
            code=_html(item["code"]),
            name=_html(item.get("name", "")),
            delta=float(item["delta"]),
        )
        for item in delta.get("score_changes", [])[:5]
    )
    valuation_items = []
    for item in delta.get("valuation_changes", [])[:5]:
        value_delta = item.get("value_delta")
        delta_text = "--" if value_delta is None else f"{float(value_delta):+.4f}"
        valuation_items.append(f"<li>{_html(item['code'])}: {_html(delta_text)}</li>")
    risk_changes = delta.get("risk_changes", {})
    holding_delta = delta.get("holding_risk_changes", {})
    provider_delta = delta.get("provider_health_delta", {})
    provider_items = "".join(
        "<li>{provider}: live rows {live:+d}, skipped rows {skipped:+d}, warnings {warnings:+d}, fallback_changed {fallback}</li>".format(
            provider=_html(provider),
            live=int(item.get("provider_live_rows_delta", 0)),
            skipped=int(item.get("provider_skipped_rows_delta", 0)),
            warnings=int(item.get("warning_count_delta", 0)),
            fallback=_html(str(item.get("fallback_changed", False))),
        )
        for provider, item in provider_delta.items()
    )
    data_quality_delta = delta.get("data_quality_grade_delta")
    data_quality_html = ""
    if data_quality_delta:
        data_quality_html = "<li>data_quality_grade: {} -> {}</li>".format(
            _html(data_quality_delta.get("previous", "unknown")),
            _html(data_quality_delta.get("current", "unknown")),
        )
    risk_text = '<p>新增 {added} 条，解除 {resolved} 条。</p>'.format(
        added=len(risk_changes.get("added", [])),
        resolved=len(risk_changes.get("resolved", [])),
    )
    holding_text = '<p>持仓风险数量 {risk_delta:+d}，市值变化 {value_delta}。</p>'.format(
        risk_delta=int(holding_delta.get("risk_count_delta", 0)),
        value_delta=_html(str(holding_delta.get("total_value_delta", "--"))),
    )
    return (
        '<section id="snapshot-delta" class="report-section">'
        '<details class="report-panel">'
        "<summary>历史快照对比</summary>"
        f'<p class="muted">对比基准: {_html(delta.get("previous_as_of", "上一期"))}</p>'
        "<h3>评分变化</h3>"
        f'<ul class="note-list">{score_items or "<li>无</li>"}</ul>'
        "<h3>估值变化</h3>"
        f'<ul class="note-list">{"".join(valuation_items) or "<li>无</li>"}</ul>'
        "<h3>风险变化</h3>"
        f"{risk_text}"
        f"{holding_text}"
        "<h3>数据质量变化</h3>"
        f'<ul class="note-list">{data_quality_html}{provider_items or ""}</ul>'
        "</details>"
        "</section>"
    )


def _render_enrichment_section(result: ResearchResult) -> str:
    if not (result.fund_details or result.nav_history_summary):
        return ""
    parts = []
    if result.fund_details:
        rows = []
        for detail in result.fund_details:
            scale = "--" if detail.scale is None else f"{detail.scale:.4f}"
            rows.append(
                [
                    _html(detail.code),
                    _html(detail.name),
                    _html(detail.fund_company or "--"),
                    _html(detail.fund_manager or "--"),
                    _html(detail.inception_date or "--"),
                    _html(scale),
                    _html(detail.rating or "--"),
                    _html(detail.source),
                ]
            )
        parts.append(
            _table(["代码", "名称", "基金公司", "基金经理", "成立日期", "规模", "评级", "来源"], rows)
        )
    if result.nav_history_summary:
        rows = []
        for code, summary in sorted(result.nav_history_summary.items()):
            rows.append(
                [
                    _html(code),
                    str(summary.get("count", 0)),
                    _html(summary.get("start_date") or "--"),
                    _html(summary.get("end_date") or "--"),
                    _format_optional_number(summary.get("latest_unit_nav")),
                    _format_optional_number(summary.get("total_return")),
                    _format_optional_number(summary.get("max_drawdown")),
                    _format_optional_number(summary.get("volatility")),
                    _html(summary.get("data_quality_grade", "unknown")),
                ]
            )
        parts.append(
            "<h3>历史净值摘要</h3>"
            + _table(
                ["代码", "样本数", "起始日期", "截止日期", "最新单位净值", "总收益", "最大回撤", "波动率", "数据质量"],
                rows,
            )
        )
    return (
        '<section id="enrichment" class="report-section">'
        '<details class="report-panel">'
        "<summary>基金详情补充数据</summary>"
        f'{"".join(parts)}'
        "</details>"
        "</section>"
    )


def _render_next_steps_section() -> str:
    items = "".join(
        f"<li>{_html(item)}</li>"
        for item in (
            "核对基金公告、基金合同、最新季报和持仓变化。",
            "对跨境/QDII 产品核对汇率、时区、申赎限制和折溢价。",
            "对短期涨幅过快的产品检查是否存在追高风险。",
        )
    )
    return (
        '<section id="next-checks" class="report-section">'
        '<details class="report-panel" open>'
        "<summary>下一步核对</summary>"
        f'<ul class="note-list">{items}</ul>'
        "</details>"
        "</section>"
    )


def _metric_card(label: str, value: str, caption: str, tone: str = "") -> str:
    tone_class = f" metric-{_html_token(tone)}" if tone else ""
    return (
        f'<article class="metric-card{tone_class}">'
        f'<span>{_html(label)}</span>'
        f'<strong>{_html(value)}</strong>'
        f'<small>{_html(caption)}</small>'
        "</article>"
    )


def _table(headers: list[str], rows: list, *, empty_text: str = "暂无数据") -> str:
    header_html = "".join(f"<th>{_html(header)}</th>" for header in headers)
    if not rows:
        return (
            '<div class="table-wrap"><table class="data-table">'
            f"<thead><tr>{header_html}</tr></thead>"
            f'<tbody><tr><td colspan="{len(headers)}">{_html(empty_text)}</td></tr></tbody>'
            "</table></div>"
        )
    body_rows = []
    for row in rows:
        row_attrs = ""
        cells = row
        if isinstance(row, _HtmlRow):
            row_attrs = row.row_attrs
        cell_html = "".join(f"<td>{cell}</td>" for cell in cells)
        attr = f" {row_attrs}" if row_attrs else ""
        body_rows.append(f"<tr{attr}>{cell_html}</tr>")
    return (
        '<div class="table-wrap"><table class="data-table">'
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table></div>"
    )


class _HtmlRow(list):
    def __init__(self, cells: list[str], *, row_attrs: str = ""):
        super().__init__(cells)
        self.row_attrs = row_attrs


def _html(value) -> str:
    return escape(str(value), quote=False)


def _html_attr(value) -> str:
    return escape(str(value), quote=True)


def _html_token(value) -> str:
    text = str(value or "neutral").lower()
    return "".join(ch if ch.isalnum() else "-" for ch in text).strip("-") or "neutral"


_REPORT_CSS = """
:root{
  --paper:#fbfaf6;
  --ink:#17202a;
  --muted:#667085;
  --line:#e4dfd4;
  --panel:#ffffff;
  --panel-soft:#f4f1e8;
  --teal:#147c72;
  --blue:#2f5f9f;
  --amber:#a66100;
  --red:#b42318;
  --green:#287c3e;
  --shadow:0 18px 45px rgba(38, 31, 21, .08);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;
  background:
    linear-gradient(135deg, rgba(20,124,114,.08), transparent 28%),
    linear-gradient(315deg, rgba(166,97,0,.08), transparent 30%),
    var(--paper);
  color:var(--ink);
  font-family:"Avenir Next","Noto Sans SC","PingFang SC",sans-serif;
  line-height:1.55;
}
a{color:var(--blue);text-decoration:none}
a:hover{text-decoration:underline}
a:focus-visible,summary:focus-visible{outline:3px solid rgba(47,95,159,.45);outline-offset:3px;border-radius:6px}
.app-shell{display:grid;grid-template-columns:240px minmax(0,1fr);gap:28px;max-width:1440px;margin:0 auto;padding:28px}
.report-sidebar{position:sticky;top:24px;align-self:start;background:rgba(255,255,255,.82);border:1px solid var(--line);border-radius:8px;padding:18px;box-shadow:var(--shadow);backdrop-filter:blur(10px)}
.brand{font-weight:800;letter-spacing:.04em;margin-bottom:18px}
.section-nav{display:grid;gap:8px}
.section-nav a{display:block;border-left:3px solid transparent;padding:7px 8px;color:var(--ink);font-weight:650}
.section-nav a:hover{background:var(--panel-soft);border-left-color:var(--teal);text-decoration:none}
.sidebar-note{margin:18px 0 0;color:var(--muted);font-size:12px}
.report-main{min-width:0}
.hero{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;padding:26px 28px;background:var(--panel);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow)}
.eyebrow{margin:0 0 6px;color:var(--teal);font-weight:800;text-transform:uppercase;font-size:12px;letter-spacing:.08em}
h1{margin:0;font-size:34px;line-height:1.15;letter-spacing:0}
h3{margin:22px 0 10px;font-size:16px}
.disclaimer{max-width:760px;margin:12px 0 0;color:var(--muted)}
.hero-status{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}
.metric-grid,.mini-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;margin:18px 0}
.mini-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
.metric-card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px;min-height:108px;display:grid;gap:4px;box-shadow:0 8px 20px rgba(38,31,21,.04)}
.metric-card span,.metric-card small{color:var(--muted)}
.metric-card strong{font-size:24px;line-height:1.1}
.metric-ok{border-top:4px solid var(--green)}
.metric-warn,.metric-warning{border-top:4px solid var(--amber)}
.metric-danger,.metric-degraded,.metric-critical{border-top:4px solid var(--red)}
.report-section{scroll-margin-top:20px;margin-top:18px}
.report-panel{background:var(--panel);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow);overflow:hidden}
.report-panel>summary{cursor:pointer;list-style:none;padding:16px 18px;font-weight:800;border-bottom:1px solid var(--line);background:linear-gradient(90deg,var(--panel),var(--panel-soft))}
.report-panel>summary::-webkit-details-marker{display:none}
.report-panel>summary:before{content:"▸";display:inline-block;margin-right:8px;color:var(--teal)}
.report-panel[open]>summary:before{content:"▾"}
.report-panel>*:not(summary){margin-left:18px;margin-right:18px}
.agent-list,.note-list,.warning-list,.risk-list{padding:0;margin:16px 18px 18px;list-style:none;display:grid;gap:10px}
.agent-list li,.note-list li,.warning-list li,.risk-list li{display:flex;gap:10px;align-items:flex-start;padding:10px 12px;background:var(--panel-soft);border-radius:8px}
.agent-name{font-weight:800;min-width:140px;color:var(--teal)}
.table-wrap{overflow:auto;margin:14px 18px 20px;border:1px solid var(--line);border-radius:8px}
.data-table{width:100%;border-collapse:collapse;background:#fff}
.data-table th{position:sticky;top:0;background:#eee8dc;text-align:left;font-size:12px;color:#4d463d;text-transform:uppercase;letter-spacing:.03em}
.data-table th,.data-table td{padding:11px 12px;border-bottom:1px solid var(--line);white-space:nowrap}
.data-table tr:hover td{background:#fbf7ed}
.fund-link{font-weight:800}
.score{font-weight:800;color:var(--teal)}
.status-pill,.severity{display:inline-flex;align-items:center;border-radius:999px;padding:3px 8px;font-size:12px;font-weight:800;border:1px solid var(--line);background:#fff;color:var(--ink);white-space:nowrap}
.status-normal,.status-ok,.status-high,.status-medium{background:#edf8f1;color:var(--green);border-color:#cce8d5}
.status-warning,.status-warn,.status-needs-checking,.severity-medium{background:#fff6e6;color:var(--amber);border-color:#f2d49b}
.status-degraded,.status-low,.status-weak,.severity-high,.severity-critical{background:#fff1f0;color:var(--red);border-color:#f4b8b2}
.severity-info{background:#eef4ff;color:var(--blue);border-color:#c9d8f2}
.valuation-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:16px 18px 20px}
.valuation-card{border:1px solid var(--line);border-radius:8px;padding:16px;background:#fff}
.valuation-card h3{margin:4px 0 0}
.valuation-value{font-size:28px;font-weight:800;color:var(--teal);margin:10px 0}
.definition-grid{display:grid;grid-template-columns:88px 1fr;gap:8px 12px;margin:0 0 12px}
.definition-grid dt{color:var(--muted)}
.definition-grid dd{margin:0;font-weight:700}
.empty-state,.muted{color:var(--muted);margin:14px 18px}
code{background:#f3efe4;border:1px solid var(--line);border-radius:6px;padding:1px 6px;font-family:"SF Mono","Menlo",monospace}
@media (max-width: 980px){
  .app-shell{grid-template-columns:1fr;padding:16px}
  .report-sidebar{position:static}
  .hero{display:block}
  .hero-status{justify-content:flex-start;margin-top:16px}
  .metric-grid,.mini-grid,.valuation-grid{grid-template-columns:1fr}
  .agent-list li,.note-list li,.warning-list li,.risk-list li{display:block}
  .agent-name{display:block;margin-bottom:4px}
}
"""


def render_json(result: ResearchResult) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _generated_at(),
        "generator": GENERATOR,
        "as_of": result.as_of,
        "data_quality_grade": result.data_quality_grade,
        "provider_health": [_provider_health_to_dict(item) for item in result.provider_health],
        "provider_warnings": [
            {
                "provider": health.provider,
                "code": warning.code,
                "message": warning.message,
                "severity": warning.severity,
                "details": warning.details,
            }
            for health in result.provider_health
            for warning in health.warnings
        ],
        "candidates": [
            {
                "code": candidate.fund.code,
                "name": candidate.fund.name,
                "category": candidate.fund.category,
                "score": candidate.total_score,
                "evidence_label": candidate.evidence_label,
                "notes": list(candidate.notes),
            }
            for candidate in result.ranked_candidates
        ],
        "valuations": {
            code: {
                "code": code,
                "method": valuation.method,
                "estimated_value": valuation.estimated_value,
                "confidence": valuation.confidence,
                "notes": list(valuation.notes),
            }
            for code, valuation in result.valuations.items()
        },
        "portfolio": _portfolio_to_json(result),
        "risk_issues": _risk_issues_to_json(result),
        "snapshot_delta": result.snapshot_delta,
        "report_metadata": {
            "format": "fund_agent_report_json",
            "schema_version": SCHEMA_VERSION,
            "disclaimer": DISCLAIMER,
        },
        "fund_details": [_fund_detail_to_json(item) for item in result.fund_details],
        "nav_history_summary": result.nav_history_summary or {},
    }


def write_json_report(result: ResearchResult, output_dir: Path | str) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    path = output_path / "fund_agent_report.json"
    path.write_text(
        json.dumps(render_json(result), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _portfolio_to_json(result: ResearchResult):
    if result.portfolio is None:
        return None
    return {
        "total_value": result.portfolio.total_value,
        "total_cost": result.portfolio.total_cost,
        "total_unrealized_return_pct": result.portfolio.total_unrealized_return_pct,
        "positions": [
            {
                "code": position.holding.code,
                "name": position.holding.name,
                "current_value": position.current_value,
                "weight": position.weight,
                "target_drift": position.target_drift,
                "unrealized_return_pct": position.unrealized_return_pct,
            }
            for position in result.portfolio.positions
        ],
    }


def _risk_issues_to_json(result: ResearchResult) -> list[dict]:
    if result.portfolio is None:
        return []
    return [
        {"code": issue.code, "severity": issue.severity, "message": issue.message}
        for issue in result.portfolio.risk_issues
    ]


def _fund_detail_to_json(detail) -> dict:
    return {
        "code": detail.code,
        "name": detail.name,
        "fund_type": detail.fund_type,
        "fund_company": detail.fund_company,
        "fund_manager": detail.fund_manager,
        "inception_date": detail.inception_date,
        "scale": detail.scale,
        "rating": detail.rating,
        "source": detail.source,
        "as_of": detail.as_of,
        "updated_at": detail.updated_at,
        "metadata": detail.metadata,
    }


def _format_optional_number(value) -> str:
    if value is None:
        return "--"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()
