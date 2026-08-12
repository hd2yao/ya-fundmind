"""User-facing view models for the local Product Web.

The existing reports and service responses keep their diagnostic provenance for
contracts and system tooling.  This module deliberately creates a smaller,
human-readable projection for ordinary product pages.
"""

from __future__ import annotations

from typing import Any

from .models import FundProfileBundle, FundRecord


_LIMITED_QUALITY_GRADES = {"critical", "degraded"}
_ATTENTION_QUALITY_GRADES = {"warning", "partial"}
_MISSING_FIELD_LABELS = {
    "fund_company": "基金公司",
    "fund_manager": "基金经理",
    "inception_date": "成立日期",
    "name": "基金名称",
    "rating": "基金评级",
    "scale": "基金规模",
}
_VALUATION_STATES = {
    "complete": ("估值已齐全", "当前持仓均已取得可用估值。"),
    "partial": ("部分持仓待估值", "部分持仓尚无可用估值，组合汇总暂不完整。"),
    "unavailable": ("当前估值暂不可用", "尚未取得持仓的可用估值，因此不展示组合总值和收益率。"),
    "not_configured": ("尚未配置持仓", "当前没有可供汇总的持仓配置。"),
}
_INTERNAL_PLACEHOLDERS = {"unknown", "none", "null", "n/a", "na", "-", "--"}


def build_market_view(intelligence: dict[str, Any], trend: dict[str, Any]) -> dict[str, Any]:
    """Build a presentation-safe market summary from existing artifacts."""

    as_of = _as_text(intelligence.get("as_of")) or _as_text(trend.get("latest_as_of"))
    quality = _as_text((intelligence.get("data_quality_summary") or {}).get("grade"))
    themes = intelligence.get("themes") or intelligence.get("top_themes") or []
    return {
        "as_of": as_of,
        "coverage": {
            "fund_count": _as_int(intelligence.get("total_funds")),
            "etf_count": _as_int(intelligence.get("total_etfs")),
        },
        "data_status": build_data_status(
            as_of=as_of,
            quality_grade=quality,
            has_data=bool(intelligence),
        ),
        "themes": [_build_theme_view(item, default_as_of=as_of) for item in themes if isinstance(item, dict)],
        "trend": {
            "persistent": _build_theme_changes(trend.get("persistent_hot_themes")),
            "new": _build_theme_changes(trend.get("new_hot_themes")),
            "rising": _build_theme_changes(trend.get("rising_themes")),
            "falling": _build_theme_changes(trend.get("falling_themes")),
        },
    }


def build_market_history_view(
    payload: dict[str, Any],
    *,
    name: str | None = None,
) -> dict[str, Any]:
    """Project one index or industry history without provider diagnostics."""

    as_of = _as_text(payload.get("as_of"))
    points = [
        {
            "date": _as_text(item.get("date")),
            "open": _as_number(item.get("open")),
            "close": _as_number(item.get("close")),
            "high": _as_number(item.get("high")),
            "low": _as_number(item.get("low")),
            "volume": _as_number(item.get("volume")),
            "turnover": _as_number(item.get("turnover")),
            "change_pct": _as_number(item.get("change_pct")),
        }
        for item in payload.get("points") or []
        if isinstance(item, dict)
    ]
    return {
        "availability": "available",
        "symbol": _as_text(payload.get("symbol")),
        "name": _display_text(payload.get("name")) or name or "市场数据",
        "range": _as_text(payload.get("range")) or "6m",
        "point_count": _as_int(payload.get("point_count")) or len(points),
        "required_points": _as_int(payload.get("required_points")),
        "points": points,
        "data_date": as_of,
        "data_status": build_data_status(
            as_of=as_of,
            quality_grade=_as_text(payload.get("data_quality_grade")),
            stale=bool(payload.get("stale")),
            fallback_used=bool(payload.get("fallback_used")),
            has_data=bool(points),
        ),
    }


def build_unavailable_market_history_view(
    *,
    symbol: str,
    name: str,
    window: str,
    description: str = "当前暂无可连续展示的历史行情。",
) -> dict[str, Any]:
    """Return a product-safe empty history instead of surfacing a provider error."""

    return {
        "availability": "missing",
        "symbol": symbol,
        "name": name,
        "range": window,
        "point_count": 0,
        "required_points": None,
        "points": [],
        "data_date": None,
        "data_status": {
            "state": "unavailable",
            "label": "历史日线暂未取得",
            "description": description,
            "as_of": None,
        },
    }


def build_market_sector_catalog_view(payload: dict[str, Any]) -> dict[str, Any]:
    """Project an industry catalog into a presentation-safe result."""

    as_of = _as_text(payload.get("as_of"))
    items = [
        {
            "symbol": _as_text(item.get("symbol")),
            "name": _display_text(item.get("name")) or "未命名板块",
            "latest": _as_number(item.get("latest")),
            "change_pct": _as_number(item.get("change_pct")),
            "rise_count": _as_int(item.get("rise_count")),
            "fall_count": _as_int(item.get("fall_count")),
            "leader_name": _display_text(item.get("leader_name")),
            "leader_change_pct": _as_number(item.get("leader_change_pct")),
        }
        for item in payload.get("items") or []
        if isinstance(item, dict) and _as_text(item.get("symbol"))
    ]
    return {
        "availability": "available",
        "items": items,
        "page": _as_int(payload.get("page")) or 1,
        "page_size": _as_int(payload.get("page_size")) or 25,
        "total": _as_int(payload.get("total")) or len(items),
        "total_pages": _as_int(payload.get("total_pages")) or (1 if items else 0),
        "query": _as_text(payload.get("query")) or "",
        "data_date": as_of,
        "data_status": build_data_status(
            as_of=as_of,
            quality_grade=_as_text(payload.get("data_quality_grade")),
            stale=bool(payload.get("stale")),
            fallback_used=bool(payload.get("fallback_used")),
            has_data=bool(items),
        ),
    }


def build_unavailable_market_sector_catalog_view(
    *,
    query: str,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    """Return a product-safe empty industry catalog without raw provider details."""

    return {
        "availability": "missing",
        "items": [],
        "page": page,
        "page_size": page_size,
        "total": 0,
        "total_pages": 0,
        "query": query,
        "data_date": None,
        "data_status": build_data_status(as_of=None, has_data=False),
    }


def build_fund_search_view(payload: dict[str, Any]) -> dict[str, Any]:
    """Map a paginated legacy explorer result without exposing provenance."""

    as_of = _as_text(payload.get("as_of"))
    items = [
        _build_fund_summary(item)
        for item in payload.get("items") or []
        if isinstance(item, dict)
    ]
    raw_facets = payload.get("facets") or {}
    raw_qualities = raw_facets.get("qualities") if isinstance(raw_facets, dict) else {}
    return {
        "availability": _availability(payload),
        "items": items,
        "page": _as_int(payload.get("page")) or 1,
        "page_size": _as_int(payload.get("page_size")) or 25,
        "total": _as_int(payload.get("total")) or 0,
        "total_pages": _as_int(payload.get("total_pages")) or 0,
        "facets": {
            "fund_types": _string_count_map(raw_facets.get("fund_types")),
            "themes": _string_count_map(raw_facets.get("themes")),
            "exchange_traded": _string_count_map(raw_facets.get("exchange_traded")),
            "purchase_statuses": _string_count_map(raw_facets.get("purchase_statuses")),
            "data_states": _quality_facets_to_data_states(raw_qualities),
        },
        "data_date": as_of,
        "data_status": build_data_status(
            as_of=as_of,
            quality_grade=_as_text(payload.get("data_quality_grade")),
            stale=bool(payload.get("index_stale")),
            has_data=_availability(payload) == "available",
        ),
    }


def fund_record_to_product_summary(
    fund: FundRecord,
    *,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Adapt the legacy ``FundRecord`` without changing its research semantics.

    The product layer intentionally omits provenance and provider metadata.  It
    only mirrors fields already carried by ``FundRecord`` and keeps unknown
    observations as ``None``.
    """

    return _build_fund_summary(
        {
            "code": fund.code,
            "name": fund.name,
            "fund_type": fund.category,
            "nav": fund.nav,
            "scale": fund.scale_billion,
            "exchange_traded": fund.exchange_traded,
            "returns": dict(fund.returns),
            "valuation_date": fund.valuation_date or fund.nav_date or as_of,
        }
    )


def build_fund_detail_view(fund: dict[str, Any], research_detail: dict[str, Any]) -> dict[str, Any]:
    """Build a detail view while preserving optional research fields as null."""

    missing = research_detail.get("missing_fields") or []
    return {
        "fund": _build_fund_summary(fund),
        "research": {
            "fund_company": _display_text(research_detail.get("fund_company")),
            "fund_manager": _display_text(research_detail.get("fund_manager")),
            "inception_date": _display_text(research_detail.get("inception_date")),
            "rating": _display_value(research_detail.get("rating")),
            "accumulated_nav": _as_number(research_detail.get("accumulated_nav")),
            "return_windows": _return_windows(research_detail.get("return_windows")),
            "coverage": _coverage_view(research_detail.get("data_coverage")),
            "missing_fields": [_missing_field_label(value) for value in missing if isinstance(value, str)],
            "is_watchlist": bool(research_detail.get("is_watchlist")),
            "is_portfolio": bool(research_detail.get("is_portfolio")),
            "data_status": build_data_status(
                as_of=_as_text(fund.get("valuation_date")) or _as_text(fund.get("as_of")),
                quality_grade=_as_text(research_detail.get("data_quality_grade")),
                has_data=bool(research_detail),
            ),
        },
    }


def build_fund_profile_view(
    bundle: FundProfileBundle,
    *,
    fallback_fund: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project profile data without provider, cache, endpoint or warning details."""

    fallback = fallback_fund or {}
    catalog = bundle.catalog
    profile = bundle.profile
    trading_rule = bundle.trading_rule
    name = _display_text(profile.name if profile is not None else None)
    if name is None:
        name = _display_text(catalog.name if catalog is not None else None)
    if name is None:
        name = _display_text(fallback.get("name"))
    fund_type = _display_text(profile.fund_type if profile is not None else None)
    if fund_type is None:
        fund_type = _display_text(catalog.fund_type if catalog is not None else None)
    if fund_type is None:
        fund_type = _display_text(fallback.get("fund_type"))

    profile_as_of = _as_text(profile.as_of if profile is not None else None)
    trading_as_of = _as_text(trading_rule.as_of if trading_rule is not None else None)
    fee_as_of = next(
        (
            value
            for fee in bundle.fees
            if (value := _as_text(fee.as_of)) is not None
        ),
        None,
    )
    catalog_as_of = _as_text(catalog.as_of if catalog is not None else None)
    as_of = profile_as_of or trading_as_of or fee_as_of or catalog_as_of
    return {
        "fund": {
            "code": bundle.code,
            "name": name,
            "fund_type": fund_type,
        },
        "profile": (
            {
                "full_name": _display_text(profile.full_name),
                "fund_company": _display_text(profile.fund_company),
                "custodian": _display_text(profile.custodian),
                "fund_manager": _display_text(profile.fund_manager),
                "issue_date": _display_text(profile.issue_date),
                "inception_date": _display_text(profile.inception_date),
                "asset_scale": _as_number(profile.asset_scale),
                "asset_scale_unit": _display_text(profile.asset_scale_unit),
                "share_scale": _as_number(profile.share_scale),
                "share_scale_unit": _display_text(profile.share_scale_unit),
                "benchmark": _display_text(profile.benchmark),
                "tracking_target": _display_text(profile.tracking_target),
            }
            if profile is not None
            else None
        ),
        "trading_rule": (
            {
                "purchase_status": _display_text(trading_rule.purchase_status),
                "redemption_status": _display_text(trading_rule.redemption_status),
                "next_open_date": _display_text(trading_rule.next_open_date),
                "minimum_purchase_amount": _display_text(
                    trading_rule.minimum_purchase_amount
                ),
                "daily_purchase_limit": _display_text(
                    trading_rule.daily_purchase_limit
                ),
                "confirmation_rule": _display_text(trading_rule.confirmation_rule),
            }
            if trading_rule is not None
            else None
        ),
        "fees": [
            {
                "fee_type": _display_text(fee.fee_type),
                "condition": _display_text(fee.condition),
                "period": _display_text(fee.period),
                "channel": _display_text(fee.channel),
                "original_rate": _display_text(fee.original_rate),
                "discounted_rate": _display_text(fee.discounted_rate),
            }
            for fee in bundle.fees
        ],
        "data_status": _build_profile_status(
            bundle.data_status,
            as_of=as_of,
            label="基金资料",
        ),
        "component_status": {
            "profile": _build_profile_status(
                bundle.profile_status,
                as_of=profile_as_of or catalog_as_of,
                label="概况",
            ),
            "trading_rule": _build_profile_status(
                bundle.trading_status,
                as_of=trading_as_of,
                label="规则",
            ),
            "fees": _build_profile_status(
                bundle.fee_status,
                as_of=fee_as_of,
                label="费率",
            ),
        },
    }


def build_unavailable_fund_profile_view(
    *,
    code: str,
    fallback_fund: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fallback = fallback_fund or {}
    unavailable = _build_profile_status("unavailable", as_of=None, label="基金资料")
    return {
        "fund": {
            "code": code,
            "name": _display_text(fallback.get("name")),
            "fund_type": _display_text(fallback.get("fund_type")),
        },
        "profile": None,
        "trading_rule": None,
        "fees": [],
        "data_status": unavailable,
        "component_status": {
            "profile": _build_profile_status("unavailable", as_of=None, label="概况"),
            "trading_rule": _build_profile_status("unavailable", as_of=None, label="规则"),
            "fees": _build_profile_status("unavailable", as_of=None, label="费率"),
        },
    }


def _build_profile_status(
    state: str,
    *,
    as_of: str | None,
    label: str,
) -> dict[str, str | None]:
    if state == "updated":
        return {
            "state": "updated",
            "label": f"{label}已更新",
            "description": f"{label}资料可供浏览。",
            "as_of": as_of,
        }
    if state == "attention":
        return {
            "state": "attention",
            "label": f"请留意{label}日期",
            "description": f"{label}资料的最新更新时间仍待确认。",
            "as_of": as_of,
        }
    if state == "unavailable":
        return {
            "state": "unavailable",
            "label": f"{label}暂未取得",
            "description": f"当前没有可展示的{label}资料，请稍后再查看。",
            "as_of": as_of,
        }
    return {
        "state": "limited",
        "label": f"{label}待补充",
        "description": f"当前仅取得部分{label}资料，请结合数据日期查看。",
        "as_of": as_of,
    }


def build_fund_history_view(payload: dict[str, Any]) -> dict[str, Any]:
    """Project NAV history points without cache/provider diagnostics."""

    as_of = _as_text(payload.get("as_of"))
    return {
        "code": _as_text(payload.get("code")),
        "range": _as_text(payload.get("range")) or "6m",
        "point_count": _as_int(payload.get("point_count")) or 0,
        "required_points": _as_int(payload.get("required_points")),
        "points": [
            {
                "date": _as_text(item.get("date")),
                "unit_nav": _as_number(item.get("unit_nav")),
                "accumulated_nav": _as_number(item.get("accumulated_nav")),
                "daily_return": _as_number(item.get("daily_return")),
            }
            for item in payload.get("points") or []
            if isinstance(item, dict)
        ],
        "data_date": as_of,
        "data_status": build_data_status(
            as_of=as_of,
            quality_grade=_as_text(payload.get("data_quality_grade")),
            stale=bool(payload.get("stale")),
            fallback_used=bool(payload.get("fallback_used")),
            has_data=bool(payload.get("points")),
        ),
    }


def build_watchlist_view(details: dict[str, Any]) -> dict[str, Any]:
    """Build the read-only configured watchlist view."""

    funds = details.get("fund_details") or details.get("funds") or []
    as_of = _as_text(details.get("as_of"))
    return {
        "as_of": as_of,
        "funds": [_build_watchlist_fund(item) for item in funds if isinstance(item, dict)],
        "detail_count": _as_int(details.get("detail_count")) or len(funds),
        "coverage_ratio": _as_number((details.get("coverage_summary") or {}).get("average_coverage_ratio")),
        "data_status": build_data_status(
            as_of=as_of,
            quality_grade=_as_text(details.get("data_quality_grade")),
            has_data=bool(details),
        ),
    }


def build_portfolio_view(payload: dict[str, Any]) -> dict[str, Any]:
    """Build the portfolio page projection without internal issue codes."""

    positions = [item for item in payload.get("positions") or [] if isinstance(item, dict)]
    holding_count = _as_int(payload.get("holding_count"))
    if holding_count is None:
        holding_count = len(positions)

    raw_valuation_status = _as_text(payload.get("valuation_status"))
    valuation_status = raw_valuation_status or ("unavailable" if holding_count else "not_configured")
    valuation_label, valuation_description = _VALUATION_STATES.get(
        valuation_status,
        ("估值状态待确认", "当前组合估值状态暂无法判断。"),
    )
    valuation_complete = valuation_status == "complete"
    valued_position_count = _as_int(payload.get("valued_position_count"))
    unvalued_position_count = _as_int(payload.get("unvalued_position_count"))
    if not valuation_complete and unvalued_position_count is None:
        unvalued_position_count = holding_count
    return {
        "as_of": _as_text(payload.get("as_of")),
        "portfolio_name": _as_text(payload.get("portfolio_name")),
        "holding_count": holding_count,
        "cash_available": _as_number(payload.get("cash_available")),
        "total_value": _as_number(payload.get("total_value")) if valuation_complete else None,
        "valued_total_value": _as_number(payload.get("valued_total_value")) if valuation_complete else None,
        "total_unrealized_return_pct": _as_number(payload.get("total_unrealized_return_pct")) if valuation_complete else None,
        "valuation": {
            "state": valuation_status,
            "label": valuation_label,
            "description": valuation_description,
            "valued_position_count": valued_position_count,
            "unvalued_position_count": unvalued_position_count,
        },
        "positions": [_build_portfolio_position(item, include_valuation=valuation_complete) for item in positions],
        "theme_exposure": _build_exposure_view(payload.get("theme_exposure"), include_valuation=valuation_complete),
        "fund_type_exposure": _build_exposure_view(payload.get("fund_type_exposure"), include_valuation=valuation_complete),
        "observations": [
            _build_portfolio_observation(item)
            for item in payload.get("observation_issues") or []
            if isinstance(item, dict)
        ],
    }


def build_data_status(
    *,
    as_of: str | None,
    quality_grade: str | None = None,
    stale: bool = False,
    fallback_used: bool = False,
    has_data: bool = True,
) -> dict[str, str | None]:
    """Convert internal data quality metadata into user-facing Chinese copy."""

    date_text = as_of or "最近一次可用日期"
    if not has_data:
        return {
            "state": "unavailable",
            "label": "暂未获取到数据",
            "description": "当前没有可展示的结构化数据，请稍后刷新。",
            "as_of": as_of,
        }
    if quality_grade in _LIMITED_QUALITY_GRADES:
        return {
            "state": "limited",
            "label": "资料暂不完整",
            "description": f"当前展示截至 {date_text} 的数据，部分资料尚待补充。",
            "as_of": as_of,
        }
    if stale or fallback_used or quality_grade in _ATTENTION_QUALITY_GRADES:
        return {
            "state": "attention",
            "label": "请留意数据日期",
            "description": f"当前展示截至 {date_text} 的数据，最新更新仍待确认。",
            "as_of": as_of,
        }
    return {
        "state": "updated",
        "label": "数据已更新",
        "description": f"当前展示截至 {date_text} 的结构化数据。",
        "as_of": as_of,
    }


def _build_fund_summary(item: dict[str, Any]) -> dict[str, Any]:
    data_date = _as_text(item.get("valuation_date")) or _as_text(item.get("as_of"))
    returns = item.get("returns") if isinstance(item.get("returns"), dict) else {}
    return {
        "code": _as_text(item.get("code")),
        "name": _display_text(item.get("name")),
        "fund_type": _display_text(item.get("fund_type")),
        "primary_theme": _display_text(item.get("primary_theme")),
        "themes": [label for value in item.get("themes") or [] if (label := _display_text(value))],
        "nav": _as_number(item.get("nav")),
        "scale": _as_number(item.get("scale")),
        "exchange_traded": bool(item.get("exchange_traded")),
        "purchase_status": _display_text(item.get("purchase_status")),
        "returns": {window: _as_number(returns.get(window)) for window in ("1m", "3m", "6m", "1y")},
        "data_date": data_date,
        "data_status": build_data_status(
            as_of=data_date,
            quality_grade=_as_text(item.get("data_quality_grade")),
            stale=bool(item.get("stale")),
            has_data=bool(item),
        ),
    }


def _build_watchlist_fund(item: dict[str, Any]) -> dict[str, Any]:
    return_windows = _return_windows(item.get("return_windows"))
    return {
        "code": _as_text(item.get("code")),
        "name": _display_text(item.get("name")),
        "fund_type": _display_text(item.get("fund_type")),
        "primary_theme": _display_text(item.get("primary_theme")),
        "nav": _as_number(item.get("nav")),
        "return_windows": return_windows,
        "coverage_ratio": _as_number((item.get("data_coverage") or {}).get("coverage_ratio")),
        "data_status": build_data_status(
            as_of=_as_text(item.get("as_of")),
            quality_grade=_as_text(item.get("data_quality_grade")),
            has_data=bool(item),
        ),
    }


def _build_theme_view(item: dict[str, Any], *, default_as_of: str | None = None) -> dict[str, Any]:
    as_of = _as_text(item.get("as_of")) or default_as_of
    return {
        "name": _display_text(item.get("theme")) or _display_text(item.get("name")) or "未分类",
        "returns": {
            "1w": _as_number(item.get("avg_return_1w")),
            "1m": _as_number(item.get("avg_return_1m")),
            "3m": _as_number(item.get("avg_return_3m")),
            "6m": _as_number(item.get("avg_return_6m")),
            "1y": _as_number(item.get("avg_return_1y")),
        },
        "positive_ratio_1m": _as_number(item.get("positive_ratio_1m")),
        "sample_size": _as_int(item.get("sample_size")),
        "fund_count": _as_int(item.get("fund_count")),
        "etf_count": _as_int(item.get("etf_count")),
        "data_status": build_data_status(
            as_of=as_of,
            quality_grade=_as_text(item.get("data_quality_grade")),
            has_data=bool(item),
        ),
    }


def _build_theme_changes(value: Any) -> list[dict[str, Any]]:
    return [
        {
            "name": _display_text(item.get("theme")) or "未分类",
            "rank": _as_int(item.get("latest_rank")),
            "rank_change": _as_int(item.get("rank_change")),
        }
        for item in value or []
        if isinstance(item, dict)
    ]


def _build_portfolio_position(item: dict[str, Any], *, include_valuation: bool) -> dict[str, Any]:
    return {
        "code": _as_text(item.get("code")),
        "name": _display_text(item.get("name")),
        "shares": _as_number(item.get("shares")),
        "cost_value": _as_number(item.get("cost_value")),
        "current_value": _as_number(item.get("current_value")) if include_valuation else None,
        "unrealized_return_pct": _as_number(item.get("unrealized_return_pct")) if include_valuation else None,
        "weight": _as_number(item.get("weight")) if include_valuation else None,
        "primary_theme": _display_text(item.get("primary_theme")),
    }


def _build_exposure_view(value: Any, *, include_valuation: bool) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    return {
        _display_text(label) or "未分类": {
            "holding_count": _as_int(item.get("holding_count")) or 0,
            "current_value": _as_number(item.get("current_value")) if include_valuation else None,
            "weight": _as_number(item.get("weight")) if include_valuation else None,
            "codes": [str(code) for code in item.get("codes") or [] if code],
        }
        for label, item in value.items()
        if isinstance(item, dict)
    }


def _build_portfolio_observation(item: dict[str, Any]) -> dict[str, str]:
    issue_type = _as_text(item.get("issue_type"))
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    if issue_type == "missing_position_valuation":
        code = _as_text(metadata.get("code"))
        return {
            "tone": "attention",
            "title": "当前估值暂不可用",
            "description": f"{code or '该持仓'} 尚未取得可用估值。",
        }
    if issue_type == "theme_overlap":
        theme = _as_text(metadata.get("theme")) or "同一主题"
        count = _as_int(item.get("holding_count")) or _as_int(metadata.get("holding_count"))
        suffix = f"，涉及 {count} 只持仓" if count else ""
        return {
            "tone": "attention",
            "title": "主题暴露重叠",
            "description": f"{theme}{suffix}。",
        }
    if issue_type == "single_holding_concentration":
        return {
            "tone": "attention",
            "title": "单只持仓占比较高",
            "description": "单只持仓在已估值部分的占比较高，建议人工核对配置。",
        }
    return {
        "tone": "attention",
        "title": "需要人工核对",
        "description": "当前组合存在一项待核对的观察信息。",
    }


def _return_windows(value: Any) -> dict[str, dict[str, float | None]]:
    if not isinstance(value, dict):
        return {}
    return {
        str(window): {
            "total_return": _as_number(item.get("total_return")),
            "max_drawdown": _as_number(item.get("max_drawdown")),
            "volatility": _as_number(item.get("volatility")),
        }
        for window, item in value.items()
        if isinstance(item, dict)
    }


def _coverage_view(value: Any) -> dict[str, Any]:
    data = value if isinstance(value, dict) else {}
    ratio = _as_number(data.get("coverage_ratio"))
    if ratio is None:
        label = "资料待补充"
    elif ratio >= 0.8:
        label = "资料较完整"
    else:
        label = "部分资料待补充"
    return {"coverage_ratio": ratio, "label": label}


def _quality_facets_to_data_states(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, int] = {}
    for quality, count in value.items():
        state = build_data_status(as_of=None, quality_grade=_as_text(quality))["state"]
        result[str(state)] = result.get(str(state), 0) + (_as_int(count) or 0)
    return result


def _string_count_map(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {
        label: _as_int(count) or 0
        for key, count in value.items()
        if (label := _display_text(key))
    }


def _missing_field_label(value: str) -> str:
    return _MISSING_FIELD_LABELS.get(value, "资料字段")


def _availability(payload: dict[str, Any]) -> str:
    return "available" if payload.get("availability") == "available" else "missing"


def _as_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _display_text(value: Any) -> str | None:
    """Drop raw upstream placeholder values from product-facing text fields."""

    text = _as_text(value)
    if text is None or text.casefold() in _INTERNAL_PLACEHOLDERS:
        return None
    return text


def _display_value(value: Any) -> str | float | int | None:
    """Keep real numeric values while dropping textual upstream placeholders."""

    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return _display_text(value)


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _as_number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
