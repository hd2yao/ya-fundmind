from __future__ import annotations

from datetime import date
from math import sqrt

from .models import FundNavPoint


def build_nav_history_summary(code: str, points: list[FundNavPoint] | tuple[FundNavPoint, ...]) -> dict:
    ordered = sorted((point for point in points if point.code == code), key=lambda item: item.date)
    if not ordered:
        return {
            "count": 0,
            "start_date": None,
            "end_date": None,
            "latest_unit_nav": None,
            "latest_accumulated_nav": None,
            "total_return": None,
            "annualized_return": None,
            "max_drawdown": None,
            "volatility": None,
            "missing_days": None,
            "source": "tiantian",
            "data_quality_grade": "degraded",
        }

    values = [point.unit_nav for point in ordered if point.unit_nav is not None and point.unit_nav > 0]
    first_value = values[0] if values else None
    last_value = values[-1] if values else None
    start_date = ordered[0].date
    end_date = ordered[-1].date
    missing_days = _missing_days(start_date, end_date, len({point.date for point in ordered}))
    returns = _daily_returns(ordered)
    total_return = None
    annualized_return = None
    if first_value and last_value:
        total_return = round((last_value / first_value - 1) * 100, 4)
        days = _days_between(start_date, end_date)
        if days and days > 0:
            annualized_return = round(((last_value / first_value) ** (365 / days) - 1) * 100, 4)

    grade = "normal"
    if len(ordered) < 2 or not values:
        grade = "degraded"
    elif missing_days and missing_days > 0:
        grade = "warning"

    latest = ordered[-1]
    return {
        "count": len(ordered),
        "start_date": start_date,
        "end_date": end_date,
        "latest_unit_nav": latest.unit_nav,
        "latest_accumulated_nav": latest.accumulated_nav,
        "total_return": total_return,
        "annualized_return": annualized_return,
        "max_drawdown": _max_drawdown(values),
        "volatility": _volatility(returns),
        "missing_days": missing_days,
        "source": latest.source or "tiantian",
        "data_quality_grade": grade,
    }


def _daily_returns(points: list[FundNavPoint]) -> list[float]:
    explicit = [point.daily_return for point in points if point.daily_return is not None]
    if explicit:
        return explicit
    returns: list[float] = []
    previous = None
    for point in points:
        if point.unit_nav is None or point.unit_nav <= 0:
            continue
        if previous:
            returns.append((point.unit_nav / previous - 1) * 100)
        previous = point.unit_nav
    return returns


def _max_drawdown(values: list[float]) -> float | None:
    if not values:
        return None
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1)
    return round(worst * 100, 4)


def _volatility(returns: list[float]) -> float | None:
    if not returns:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((item - mean) ** 2 for item in returns) / len(returns)
    return round(sqrt(variance), 4)


def _missing_days(start_date: str, end_date: str, observed_count: int) -> int | None:
    days = _days_between(start_date, end_date)
    if days is None:
        return None
    return max(0, days + 1 - observed_count)


def _days_between(start_date: str, end_date: str) -> int | None:
    try:
        return (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days
    except ValueError:
        return None
