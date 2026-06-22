from __future__ import annotations

from dataclasses import dataclass

from .models import FundRecord, ScoredFund, ValuationResult
from .portfolio import PortfolioHolding, PortfolioSummary, analyze_portfolio
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


def run_research(
    funds: list[FundRecord],
    *,
    holdings: list[PortfolioHolding] | None = None,
    as_of: str = "",
    candidate_limit: int = 5,
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
    )
