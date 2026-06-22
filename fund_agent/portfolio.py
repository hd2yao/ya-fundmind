from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .models import ValuationResult


@dataclass(frozen=True)
class PortfolioHolding:
    code: str
    name: str
    shares: float
    cost_nav: float
    buy_date: str
    target_weight: float | None = None
    notes: str = ""


@dataclass(frozen=True)
class PortfolioPosition:
    holding: PortfolioHolding
    valuation: ValuationResult | None
    current_value: float
    cost_value: float
    unrealized_return_pct: float
    weight: float
    target_drift: float | None


@dataclass(frozen=True)
class RiskIssue:
    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class PortfolioSummary:
    total_value: float
    total_cost: float
    total_unrealized_return_pct: float
    positions: tuple[PortfolioPosition, ...]
    risk_issues: tuple[RiskIssue, ...]


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _round_money(value: float) -> float:
    return round(value, 2)


def analyze_portfolio(
    holdings: list[PortfolioHolding],
    valuations: dict[str, ValuationResult],
    *,
    as_of: str | None = None,
    max_stale_days: int = 7,
    concentration_limit: float = 0.35,
    drift_limit: float = 0.10,
) -> PortfolioSummary:
    raw_positions: list[tuple[PortfolioHolding, ValuationResult | None, float, float, float]] = []
    issues: list[RiskIssue] = []

    for holding in holdings:
        valuation = valuations.get(holding.code)
        unit_value = valuation.estimated_value if valuation else None
        if unit_value is None:
            current_value = 0.0
            issues.append(
                RiskIssue(
                    code=holding.code,
                    severity="High",
                    message=f"{holding.name} 缺少可用估值，无法计算当前市值。",
                )
            )
        else:
            current_value = holding.shares * unit_value
        cost_value = holding.shares * holding.cost_nav
        unrealized = 0.0 if cost_value == 0 else (current_value / cost_value - 1) * 100
        raw_positions.append((holding, valuation, current_value, cost_value, unrealized))

    total_value = sum(item[2] for item in raw_positions)
    total_cost = sum(item[3] for item in raw_positions)
    positions: list[PortfolioPosition] = []
    as_of_date = _parse_date(as_of)

    for holding, valuation, current_value, cost_value, unrealized in raw_positions:
        weight = 0.0 if total_value == 0 else current_value / total_value
        target_drift = None
        if holding.target_weight is not None:
            target_drift = weight - holding.target_weight
            if abs(target_drift) > drift_limit:
                issues.append(
                    RiskIssue(
                        code=holding.code,
                        severity="Medium",
                        message=f"{holding.name} 目标权重偏离 {target_drift:.1%}，需要再平衡检查。",
                    )
                )
        if weight > concentration_limit:
            issues.append(
                RiskIssue(
                    code=holding.code,
                    severity="High",
                    message=f"{holding.name} 单只集中度 {weight:.1%}，高于上限 {concentration_limit:.0%}。",
                )
            )
        if valuation and as_of_date:
            nav_date = _parse_date(valuation.fund.nav_date)
            if nav_date is None:
                issues.append(
                    RiskIssue(
                        code=holding.code,
                        severity="Medium",
                        message=f"{holding.name} 缺少净值日期，数据新鲜度需要核对。",
                    )
                )
            elif (as_of_date - nav_date).days > max_stale_days:
                issues.append(
                    RiskIssue(
                        code=holding.code,
                        severity="Medium",
                        message=f"{holding.name} 数据陈旧：净值日 {nav_date.isoformat()}。",
                    )
                )

        positions.append(
            PortfolioPosition(
                holding=holding,
                valuation=valuation,
                current_value=_round_money(current_value),
                cost_value=_round_money(cost_value),
                unrealized_return_pct=round(unrealized, 2),
                weight=round(weight, 4),
                target_drift=None if target_drift is None else round(target_drift, 4),
            )
        )

    total_return = 0.0 if total_cost == 0 else (total_value / total_cost - 1) * 100
    return PortfolioSummary(
        total_value=_round_money(total_value),
        total_cost=_round_money(total_cost),
        total_unrealized_return_pct=round(total_return, 2),
        positions=tuple(positions),
        risk_issues=tuple(issues),
    )
