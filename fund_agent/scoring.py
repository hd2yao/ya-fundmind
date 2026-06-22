from __future__ import annotations

import math
from statistics import mean, pstdev

from .models import FundRecord, ScoreBreakdown, ScoredFund


RETURN_WEIGHTS = {
    "1w": 0.05,
    "1m": 0.15,
    "3m": 0.25,
    "6m": 0.25,
    "1y": 0.30,
}


def _ret(fund: FundRecord, period: str) -> float:
    return float(fund.returns.get(period, 0.0) or 0.0)


def _bounded(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _return_quality(fund: FundRecord) -> float:
    weighted = 0.0
    for period, weight in RETURN_WEIGHTS.items():
        raw = _ret(fund, period)
        penalty_adjusted = raw * (1 + abs(raw) / 40.0) if raw < 0 else raw
        weighted += penalty_adjusted * weight
    return _bounded(weighted * 2.0, high=45.0)


def _trend_quality(fund: FundRecord) -> float:
    annualized = [
        _ret(fund, "1w") * 52,
        _ret(fund, "1m") * 12,
        _ret(fund, "3m") * 4,
        _ret(fund, "6m") * 2,
        _ret(fund, "1y"),
    ]
    avg = mean(annualized)
    spread = pstdev(annualized)
    if abs(avg) < 1:
        return 0.0
    coefficient = spread / (abs(avg) + 1)
    return _bounded(25.0 - coefficient * 18.0, high=25.0)


def _momentum_confirmation(fund: FundRecord) -> float:
    periods = ("1m", "3m", "6m", "1y")
    positives = sum(1 for period in periods if _ret(fund, period) > 0)
    return positives / len(periods) * 15.0


def _risk_adjusted(fund: FundRecord) -> float:
    values = [_ret(fund, period) for period in ("1m", "3m", "6m", "1y")]
    avg = mean(values)
    spread = pstdev(values)
    if avg <= 0 or spread < 0.01:
        return 0.0
    return _bounded((avg / (spread + 1.0)) * 6.0, high=15.0)


def _scale_quality(fund: FundRecord) -> tuple[float, str | None]:
    scale = fund.scale_billion
    if scale is None:
        return 3.0, "规模数据缺失，降低证据强度"
    if scale < 2:
        return 1.0, "规模小于 2 亿元，流动性和清盘风险较高"
    if scale < 10:
        return 5.0, "规模偏小，需要关注流动性"
    if scale > 120:
        return 8.0, "规模较大，风格漂移和调仓效率需跟踪"
    return 10.0, None


def _anti_sprint_penalty(fund: FundRecord) -> float:
    one_month = abs(_ret(fund, "1m"))
    three_month = abs(_ret(fund, "3m"))
    monthly_average = three_month / 3.0 if three_month > 1 else 1.0
    ratio = one_month / monthly_average if monthly_average > 0 else 1.0
    weekly_surge = max(0.0, _ret(fund, "1w") - 6.0) * 0.7
    return _bounded(max(0.0, ratio - 2.0) * 4.0 + weekly_surge, high=18.0)


def _evidence_label(fund: FundRecord) -> str:
    missing = [
        fund.nav is None,
        not fund.returns,
        fund.scale_billion is None,
    ]
    if sum(missing) == 0:
        return "Medium"
    if sum(missing) == 1:
        return "Needs checking"
    return "Weak"


def score_fund(fund: FundRecord) -> ScoredFund:
    return_quality = _return_quality(fund)
    trend_quality = _trend_quality(fund)
    momentum = _momentum_confirmation(fund)
    risk_adjusted = _risk_adjusted(fund)
    scale_quality, scale_note = _scale_quality(fund)
    sprint_penalty = _anti_sprint_penalty(fund)
    total = (
        return_quality
        + trend_quality
        + momentum
        + risk_adjusted
        + scale_quality
        - sprint_penalty
    )
    if any(_ret(fund, period) < 0 for period in ("6m", "1y")):
        total -= 6.0
    notes = tuple(note for note in (scale_note,) if note)
    breakdown = ScoreBreakdown(
        return_quality=round(return_quality, 2),
        trend_quality=round(trend_quality, 2),
        momentum_confirmation=round(momentum, 2),
        risk_adjusted=round(risk_adjusted, 2),
        scale_quality=round(scale_quality, 2),
        anti_sprint_penalty=round(sprint_penalty, 2),
    )
    return ScoredFund(
        fund=fund,
        total_score=round(_bounded(total), 2),
        breakdown=breakdown,
        evidence_label=_evidence_label(fund),
        notes=notes,
    )


def rank_funds(funds: list[FundRecord], limit: int | None = None) -> list[ScoredFund]:
    ranked = sorted(
        (score_fund(fund) for fund in funds),
        key=lambda item: (item.total_score, item.fund.scale_billion or 0.0),
        reverse=True,
    )
    return ranked[:limit] if limit else ranked
