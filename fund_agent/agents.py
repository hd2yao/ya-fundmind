from __future__ import annotations

from dataclasses import dataclass, replace

from .models import FundRecord, ProviderHealth, ScoredFund, ValuationResult
from .portfolio import PortfolioHolding, PortfolioSummary, RiskIssue, analyze_portfolio
from .scoring import rank_funds
from .valuation import estimate_value


@dataclass(frozen=True)
class AgentTrace:
    agent_name: str
    summary: str


@dataclass(frozen=True)
class ResearchResult:
    as_of: str
    ranked_candidates: tuple[ScoredFund, ...]
    valuations: dict[str, ValuationResult]
    portfolio: PortfolioSummary | None
    traces: tuple[AgentTrace, ...]
    provider_health: tuple[ProviderHealth, ...] = ()
    snapshot_delta: dict | None = None

    @property
    def data_quality_grade(self) -> str:
        if any(health.has_critical_warnings for health in self.provider_health):
            return "degraded"
        if any(warning.severity == "warning" for health in self.provider_health for warning in health.warnings):
            return "warning"
        if any(valuation.fund.metadata.get("stale") for valuation in self.valuations.values()):
            return "warning"
        return "normal"


def run_research(
    funds: list[FundRecord],
    *,
    holdings: list[PortfolioHolding] | None = None,
    as_of: str = "",
    candidate_limit: int = 5,
    provider_health: tuple[ProviderHealth, ...] = (),
) -> ResearchResult:
    traces: list[AgentTrace] = [
        AgentTrace("DataAgent", f"已标准化 {len(funds)} 只基金/ETF。")
    ]

    ranked = tuple(rank_funds(funds, limit=candidate_limit))
    traces.append(
        AgentTrace("ScreeningAgent", f"生成 {len(ranked)} 个研究优先级候选。")
    )

    valuations = {fund.code: estimate_value(fund) for fund in funds}
    high_confidence = sum(1 for item in valuations.values() if item.confidence == "High")
    traces.append(
        AgentTrace("ValuationAgent", f"完成 {len(valuations)} 个估值分类，其中高置信 {high_confidence} 个。")
    )

    portfolio = None
    if holdings:
        portfolio = analyze_portfolio(
            holdings,
            valuations,
            as_of=as_of or None,
            concentration_limit=0.35,
        )
        data_quality_issues = _data_quality_risk_issues(provider_health, valuations)
        if data_quality_issues:
            portfolio = replace(
                portfolio,
                risk_issues=(*data_quality_issues, *portfolio.risk_issues),
            )
        traces.append(
            AgentTrace("RiskAgent", f"识别 {len(portfolio.risk_issues)} 条组合风险提示。")
        )
        traces.append(
            AgentTrace("PortfolioAgent", f"组合市值 {portfolio.total_value:.2f}，浮动收益 {portfolio.total_unrealized_return_pct:.2f}%。")
        )
    else:
        traces.append(AgentTrace("RiskAgent", "未提供持仓文件，仅输出候选和估值风险。"))

    traces.append(AgentTrace("ReportAgent", "生成研究报告，不包含自动交易指令。"))
    return ResearchResult(
        as_of=as_of,
        ranked_candidates=ranked,
        valuations=valuations,
        portfolio=portfolio,
        traces=tuple(traces),
        provider_health=provider_health,
    )


def _data_quality_risk_issues(
    provider_health: tuple[ProviderHealth, ...],
    valuations: dict[str, ValuationResult],
) -> tuple[RiskIssue, ...]:
    issues: list[RiskIssue] = []
    for health in provider_health:
        if health.fallback_used:
            issues.append(
                RiskIssue(
                    code="DATA_QUALITY",
                    severity="Medium",
                    message=f"{health.provider} 使用 fallback 数据源 {health.fallback_source or '--'}；reason={health.fallback_reason or '--'}。",
                )
            )
        if health.watchlist_missing_codes:
            severity = "High" if health.watchlist_matched_count == 0 else "Medium"
            issues.append(
                RiskIssue(
                    code="DATA_QUALITY",
                    severity=severity,
                    message=f"watchlist 缺失代码: {', '.join(health.watchlist_missing_codes)}。",
                )
            )
        for warning in health.warnings:
            if warning.severity == "critical":
                issues.append(
                    RiskIssue(
                        code="DATA_QUALITY",
                        severity="High",
                        message=f"critical provider warning `{warning.code}`: {warning.message}",
                    )
                )
    stale_codes = [
        code
        for code, valuation in valuations.items()
        if valuation.fund.metadata.get("stale")
    ]
    if stale_codes:
        issues.append(
            RiskIssue(
                code="DATA_QUALITY",
                severity="High",
                message=f"stale cache data used for: {', '.join(stale_codes)}。",
            )
        )
    return tuple(issues)
