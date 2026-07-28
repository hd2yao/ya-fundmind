from __future__ import annotations

from fund_agent.product_views import (
    build_fund_detail_view,
    build_fund_history_view,
    build_fund_search_view,
    build_market_view,
    build_market_history_view,
    build_market_sector_catalog_view,
    build_portfolio_view,
    fund_record_to_product_summary,
)
from fund_agent.models import FundRecord
from fund_agent.scoring import score_fund


def test_product_fund_search_hides_diagnostics_and_keeps_missing_values_unknown():
    view = build_fund_search_view(
        {
            "availability": "available",
            "items": [
                {
                    "code": "510300",
                    "name": "沪深300ETF",
                    "fund_type": "ETF",
                    "nav": None,
                    "scale": None,
                    "exchange_traded": True,
                    "returns": {"1m": None},
                    "source": "cache:akshare",
                    "as_of": "2026-07-27",
                    "updated_at": "2026-07-28T01:00:00+00:00",
                    "expires_at": "2026-07-29T01:00:00+00:00",
                    "stale": True,
                    "data_quality_grade": "normal",
                }
            ],
            "page": 1,
            "page_size": 25,
            "total": 1,
            "total_pages": 1,
            "facets": {"fund_types": {"ETF": 1}, "themes": {}, "exchange_traded": {"true": 1}, "qualities": {"normal": 1}},
            "as_of": "2026-07-27",
            "source": "cache:akshare",
            "data_quality_grade": "normal",
            "index_stale": True,
            "warnings": ["fund_explorer_source_missing_using_last_good_index"],
        }
    )

    item = view["items"][0]

    assert item["nav"] is None
    assert item["scale"] is None
    assert item["returns"]["1m"] is None
    assert item["data_status"] == {
        "state": "attention",
        "label": "请留意数据日期",
        "description": "当前展示截至 2026-07-27 的数据，最新更新仍待确认。",
        "as_of": "2026-07-27",
    }
    _assert_no_diagnostics(view)


def test_product_market_maps_internal_quality_to_chinese_state():
    view = build_market_view(
        {
            "as_of": "2026-07-27",
            "total_funds": 21600,
            "total_etfs": 3500,
            "source": "akshare",
            "data_quality_summary": {"grade": "degraded", "warnings": ["raw_code"]},
            "themes": [
                {
                    "theme": "人工智能",
                    "avg_return_1m": 5.2,
                    "sample_size": 2,
                    "data_quality_grade": "degraded",
                }
            ],
        },
        {"persistent_hot_themes": [{"theme": "人工智能", "latest_rank": 1}]},
    )

    assert view["data_status"]["state"] == "limited"
    assert view["data_status"]["label"] == "资料暂不完整"
    assert view["themes"][0]["data_status"]["label"] == "资料暂不完整"
    assert view["coverage"] == {"fund_count": 21600, "etf_count": 3500}
    _assert_no_diagnostics(view)


def test_product_market_replaces_raw_upstream_placeholder_values():
    view = build_market_view(
        {
            "as_of": "2026-07-27",
            "themes": [{"theme": "unknown", "avg_return_1m": 1.2, "sample_size": 3}],
        },
        {"persistent_hot_themes": [{"theme": "unknown", "latest_rank": 1}]},
    )

    assert view["themes"][0]["name"] == "未分类"
    assert view["trend"]["persistent"][0]["name"] == "未分类"
    assert "unknown" not in str(view).lower()


def test_product_market_history_and_sector_catalog_hide_provider_diagnostics():
    history = build_market_history_view(
        {
            "symbol": "000300",
            "name": "沪深300",
            "range": "6m",
            "point_count": 1,
            "points": [{"date": "2026-07-27", "close": 4702.43, "source": "cache:akshare"}],
            "as_of": "2026-07-27",
            "source": "cache:akshare",
            "stale": True,
            "fallback_used": True,
            "data_quality_grade": "warning",
        }
    )
    catalog = build_market_sector_catalog_view(
        {
            "items": [{"symbol": "BK1607", "name": "医药流通", "latest": 1961.48, "source": "akshare"}],
            "source": "akshare",
            "as_of": "2026-07-27",
            "stale": False,
            "data_quality_grade": "normal",
        }
    )

    assert history["data_status"]["label"] == "请留意数据日期"
    assert catalog["items"][0]["name"] == "医药流通"
    _assert_no_diagnostics(history)
    _assert_no_diagnostics(catalog)


def test_product_fund_detail_converts_missing_fields_to_user_labels():
    view = build_fund_detail_view(
        {
            "code": "510300",
            "name": "沪深300ETF",
            "fund_type": "ETF",
            "source": "akshare",
            "as_of": "2026-07-27",
            "metadata": {"secret": "must-not-leak"},
        },
        {
            "fund_company": "华泰柏瑞基金",
            "missing_fields": ["rating", "fund_manager"],
            "data_quality_grade": "warning",
            "data_quality_warnings": ["internal_warning"],
        },
    )

    assert view["research"]["missing_fields"] == ["基金评级", "基金经理"]
    assert view["research"]["data_status"]["state"] == "attention"
    _assert_no_diagnostics(view)


def test_product_fund_detail_drops_upstream_placeholder_values():
    view = build_fund_detail_view(
        {
            "code": "510300",
            "name": "沪深300ETF",
            "fund_type": "ETF",
            "valuation_date": "2026-07-27",
        },
        {
            "fund_company": "unknown",
            "fund_manager": "--",
            "inception_date": "N/A",
            "rating": "null",
            "accumulated_nav": "not-a-number",
        },
    )

    assert view["research"]["fund_company"] is None
    assert view["research"]["fund_manager"] is None
    assert view["research"]["inception_date"] is None
    assert view["research"]["rating"] is None
    assert view["research"]["accumulated_nav"] is None


def test_product_history_and_portfolio_do_not_turn_unknown_into_zero_or_leak_source():
    history = build_fund_history_view(
        {
            "code": "510300",
            "range": "3m",
            "point_count": 1,
            "points": [{"date": "2026-07-27", "unit_nav": None, "source": "cache:akshare"}],
            "source": "cache:akshare",
            "as_of": "2026-07-27",
            "stale": True,
            "fallback_used": True,
            "data_quality_grade": "warning",
            "warnings": [{"code": "live_fallback", "message": "raw"}],
        }
    )
    portfolio = build_portfolio_view(
        {
            "as_of": "2026-07-27",
            "portfolio_name": "我的组合",
            "holding_count": 1,
            "valuation_status": "unavailable",
            "total_value": None,
            "valued_total_value": 0,
            "positions": [
                {
                    "code": "510300",
                    "name": "沪深300ETF",
                    "current_value": None,
                    "weight": None,
                    "source": "cache:akshare",
                }
            ],
            "warnings": ["portfolio_current_value_unavailable"],
            "observation_issues": [
                {
                    "issue_type": "missing_position_valuation",
                    "severity": "warning",
                    "message": "510300 has no usable current valuation.",
                }
            ],
        }
    )

    assert history["points"][0]["unit_nav"] is None
    assert history["data_status"]["label"] == "请留意数据日期"
    assert portfolio["valuation"]["label"] == "当前估值暂不可用"
    assert portfolio["total_value"] is None
    assert portfolio["positions"][0]["current_value"] is None
    assert portfolio["observations"][0]["title"] == "当前估值暂不可用"
    _assert_no_diagnostics(history)
    _assert_no_diagnostics(portfolio)


def test_product_portfolio_treats_legacy_missing_valuation_as_unknown_not_zero():
    view = build_portfolio_view(
        {
            "as_of": "2026-07-27",
            "portfolio_name": "我的组合",
            "holding_count": 1,
            "valuation_status": None,
            "total_value": 0,
            "valued_total_value": None,
            "total_unrealized_return_pct": -100,
            "positions": [
                {
                    "code": "510300",
                    "name": "沪深300ETF",
                    "shares": 800,
                    "cost_value": 2960,
                    "current_value": 0,
                    "unrealized_return_pct": -100,
                    "weight": 0,
                }
            ],
            "theme_exposure": {
                "沪深300": {"holding_count": 1, "current_value": 0, "weight": 0}
            },
        }
    )

    assert view["valuation"]["state"] == "unavailable"
    assert view["total_value"] is None
    assert view["valued_total_value"] is None
    assert view["total_unrealized_return_pct"] is None
    assert view["positions"][0]["current_value"] is None
    assert view["positions"][0]["unrealized_return_pct"] is None
    assert view["positions"][0]["weight"] is None
    assert view["theme_exposure"]["沪深300"]["current_value"] is None
    assert view["theme_exposure"]["沪深300"]["weight"] is None


def test_legacy_fund_record_adapter_preserves_unknown_values_without_provenance():
    view = fund_record_to_product_summary(
        FundRecord(
            code="510300",
            name="沪深300ETF",
            category="ETF",
            nav=None,
            scale_billion=None,
            returns={"1m": None},
            source="cache:akshare",
        ),
        as_of="2026-07-27",
    )

    assert view["nav"] is None
    assert view["scale"] is None
    assert view["returns"]["1m"] is None
    assert view["data_date"] == "2026-07-27"
    _assert_no_diagnostics(view)


def test_legacy_fund_record_adapter_keeps_the_v26_score_snapshot_unchanged():
    fund = FundRecord(
        code="510300",
        name="沪深300ETF",
        category="ETF",
        nav=4.7,
        returns={"1w": 1.2, "1m": 3.4, "3m": 7.8, "6m": 12.5, "1y": 18.0},
        scale_billion=56.0,
        source="akshare",
    )

    before = score_fund(fund)
    fund_record_to_product_summary(fund, as_of="2026-07-27")
    after = score_fund(fund)

    assert before.total_score == 74.22
    assert after == before


def _assert_no_diagnostics(value):
    forbidden = {
        "source",
        "updated_at",
        "expires_at",
        "stale",
        "fallback_used",
        "fallback_reason",
        "data_quality_grade",
        "data_quality_warnings",
        "warnings",
        "schema_version",
        "metadata",
    }
    if isinstance(value, dict):
        assert not (set(value) & forbidden)
        for child in value.values():
            _assert_no_diagnostics(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_diagnostics(child)
