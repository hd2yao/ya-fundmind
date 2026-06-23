from __future__ import annotations

from html import escape

from .agents import ResearchResult


DISCLAIMER = "本报告仅用于研究辅助，不构成投资建议，不包含任何自动交易指令。"


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
            for provider, warning in warnings:
                lines.append(
                    f"- **{warning.severity}** `{provider}:{warning.code}`: {warning.message}"
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
    markdown = render_markdown(result)
    rows = "\n".join(f"<p>{escape(line)}</p>" if line else "<br>" for line in markdown.splitlines())
    return (
        "<!doctype html>\n"
        "<html lang=\"zh-CN\">\n"
        "<head><meta charset=\"utf-8\"><title>YA FundMind 基金智研系统日报</title>"
        "<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:960px;margin:32px auto;line-height:1.6;color:#17202a}"
        "p{margin:6px 0} table{border-collapse:collapse} code{background:#f4f6f7;padding:2px 4px}</style></head>\n"
        f"<body>{rows}</body>\n"
        "</html>\n"
    )
