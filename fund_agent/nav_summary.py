from __future__ import annotations

from datetime import date
from math import sqrt

from .models import FundNavPoint

SUPPORTED_NAV_WINDOWS = ("1m", "3m", "6m", "1y", "all")
DEFAULT_NAV_WINDOWS = ("1m", "3m", "6m")
REQUIRED_NAV_POINTS_BY_WINDOW = {
    "1m": 20,
    "3m": 60,
    "6m": 120,
    "1y": 240,
}


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
        "metadata": _summary_metadata(ordered, start_date, end_date),
    }


def build_nav_history_windows_summary(
    code: str,
    points: list[FundNavPoint] | tuple[FundNavPoint, ...],
    *,
    windows: tuple[str, ...] = DEFAULT_NAV_WINDOWS,
    as_of: str | None = None,
) -> dict:
    normalized_windows = tuple(_normalize_window(window) for window in windows)
    ordered = sorted((point for point in points if point.code == code), key=lambda item: item.date)
    anchor_date = as_of or (ordered[-1].date if ordered else None)
    base = build_nav_history_summary(code, ordered)
    window_summaries = {}
    for window in normalized_windows:
        summary = build_nav_history_summary(
            code,
            _points_for_window(ordered, window=window, anchor_date=anchor_date),
        )
        required_points = REQUIRED_NAV_POINTS_BY_WINDOW.get(window, len(_points_for_window(ordered, window=window)))
        metadata = {
            **summary.get("metadata", {}),
            "required_points": required_points,
            "actual_points": summary.get("count", 0),
            "window_mode": "nav_points",
        }
        summary = {**summary, "metadata": metadata}
        if summary.get("data_quality_grade") == "normal" and metadata.get("annualized_return_unstable"):
            summary = {**summary, "data_quality_grade": "warning"}
        if window != "all" and summary.get("count", 0) < required_points:
            grade = "degraded" if summary.get("count", 0) < 2 else "warning"
            summary = {**summary, "data_quality_grade": grade}
        window_summaries[window] = summary
    return {
        **base,
        "windows_requested": list(normalized_windows),
        "windows_generated": list(window_summaries.keys()),
        "windows": window_summaries,
    }


def parse_nav_windows(value: str | None) -> tuple[str, ...]:
    if value is None or not str(value).strip():
        return DEFAULT_NAV_WINDOWS
    windows = tuple(item.strip().lower() for item in str(value).split(",") if item.strip())
    if not windows:
        return DEFAULT_NAV_WINDOWS
    return tuple(_normalize_window(window) for window in windows)


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


def _normalize_window(window: str) -> str:
    normalized = str(window).strip().lower()
    if normalized not in SUPPORTED_NAV_WINDOWS:
        raise ValueError(f"Unsupported nav window: {window}. Supported windows: {', '.join(SUPPORTED_NAV_WINDOWS)}")
    return normalized


def _points_for_window(
    points: list[FundNavPoint],
    *,
    window: str,
    anchor_date: str | None = None,
) -> list[FundNavPoint]:
    valid_points = [point for point in points if point.unit_nav is not None and point.unit_nav > 0]
    if window == "all":
        return points
    required_points = REQUIRED_NAV_POINTS_BY_WINDOW[window]
    return valid_points[-required_points:]


def _summary_metadata(points: list[FundNavPoint], start_date: str, end_date: str) -> dict:
    days = _days_between(start_date, end_date)
    unstable = days is None or days < 30 or len(points) < 20
    metadata = {"annualized_return_unstable": unstable}
    if unstable:
        metadata["annualized_return_note"] = "短样本年化收益不稳定，仅用于观察。"
    return metadata
