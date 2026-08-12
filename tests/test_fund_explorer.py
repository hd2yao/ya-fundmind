from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fund_agent.cache import FundCache
from fund_agent.fund_explorer import FundExplorerIndex, FundSearchQuery
from fund_agent.models import FundCatalogEntry, FundTradingRule


def _write_market_report(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "as_of": "2026-07-21",
                "source": "akshare",
                "data_quality_summary": {"grade": "warning"},
                "warnings": ["insufficient_sample_themes:1"],
                "records": [
                    {
                        "code": "SH510300",
                        "name": "沪深300ETF华泰柏瑞",
                        "fund_type": "ETF",
                        "nav": 4.21,
                        "scale": 520.5,
                        "exchange_traded": True,
                        "source": "akshare",
                        "as_of": "2026-07-21",
                        "valuation_date": "2026-07-21",
                        "metadata": {
                            "returns": {"1m": 2.5, "3m": 5.0, "6m": 8.0, "1y": 12.0},
                            "stale": False,
                            "updated_at": "2026-07-21T13:30:00+00:00",
                            "expires_at": "2026-07-22T13:30:00+00:00",
                            "secret": "must-not-leak",
                        },
                    },
                    {
                        "code": "000001",
                        "name": "华夏成长混合",
                        "fund_type": "混合型",
                        "nav": 1.23,
                        "scale": None,
                        "exchange_traded": False,
                        "source": "cache:akshare",
                        "as_of": "2026-07-20",
                        "valuation_date": "2026-07-20",
                        "metadata": {
                            "returns": {"1m": -1.5, "3m": 0.5},
                            "stale": True,
                            "updated_at": "2026-07-20T13:30:00+00:00",
                            "expires_at": "2026-07-21T13:30:00+00:00",
                        },
                    },
                    {
                        "code": "000002",
                        "name": None,
                        "fund_type": None,
                        "metadata": {},
                    },
                ],
                "classifications": [
                    {
                        "code": "510300",
                        "primary_theme": "宽基",
                        "themes": ["宽基", "沪深300"],
                        "confidence": 0.95,
                    },
                    {
                        "code": "000001",
                        "primary_theme": "成长",
                        "themes": ["成长"],
                        "confidence": 0.7,
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _write_profile_reference_cache(path: Path) -> FundCache:
    cache = FundCache(path)
    now = datetime(2026, 7, 21, 14, 0, tzinfo=timezone.utc)
    cache.replace_fund_catalog_snapshot(
        [
            FundCatalogEntry(
                code="510300",
                name="目录版沪深300ETF",
                fund_type="ETF-指数型",
                exchange_traded=True,
                catalog_sources=("fund_name_em", "fund_etf_spot_em"),
                source="akshare",
            ),
            FundCatalogEntry(
                code="021511",
                name="创新药混合A",
                fund_type="混合型",
                exchange_traded=False,
                catalog_sources=("fund_name_em", "fund_open_fund_rank_em"),
                source="akshare",
            ),
        ],
        snapshot_id="catalog-v1",
        as_of="2026-07-21",
        ttl_days=30,
        now=now,
    )
    cache.replace_purchase_snapshot(
        [
            FundTradingRule(
                code="510300",
                purchase_status="场内交易",
                redemption_status="场内交易",
                source="akshare",
            ),
            FundTradingRule(
                code="021511",
                purchase_status="开放申购",
                redemption_status="开放赎回",
                source="akshare",
            ),
        ],
        snapshot_id="purchase-v1",
        as_of="2026-07-21",
        ttl_days=30,
        now=now,
    )
    return cache


def test_search_normalizes_and_merges_market_records(tmp_path: Path) -> None:
    report_path = tmp_path / "market" / "market_intelligence_report.json"
    _write_market_report(report_path)
    index = FundExplorerIndex(report_path)

    result = index.search(FundSearchQuery(q="510300"))

    assert result["total"] == 1
    assert result["items"][0] == {
        "code": "510300",
        "name": "沪深300ETF华泰柏瑞",
        "fund_type": "ETF",
        "primary_theme": "宽基",
        "themes": ["宽基", "沪深300"],
        "classification_confidence": 0.95,
        "nav": 4.21,
        "scale": 520.5,
        "exchange_traded": True,
        "returns": {"1m": 2.5, "3m": 5.0, "6m": 8.0, "1y": 12.0},
        "source": "akshare",
        "as_of": "2026-07-21",
        "valuation_date": "2026-07-21",
        "updated_at": "2026-07-21T13:30:00+00:00",
        "expires_at": "2026-07-22T13:30:00+00:00",
        "stale": False,
        "data_quality_grade": "normal",
    }
    assert "secret" not in json.dumps(result, ensure_ascii=False)


@pytest.mark.parametrize(
    ("query", "expected_codes"),
    [
        (FundSearchQuery(q="成长"), ["000001"]),
        (FundSearchQuery(fund_type="ETF"), ["510300"]),
        (FundSearchQuery(theme="成长"), ["000001"]),
        (FundSearchQuery(exchange_traded=True), ["510300"]),
        (FundSearchQuery(quality="warning"), ["000001"]),
    ],
)
def test_search_supports_filters(
    tmp_path: Path,
    query: FundSearchQuery,
    expected_codes: list[str],
) -> None:
    report_path = tmp_path / "market.json"
    _write_market_report(report_path)

    result = FundExplorerIndex(report_path).search(query)

    assert [item["code"] for item in result["items"]] == expected_codes


def test_search_unions_catalog_with_market_and_uses_catalog_identity(tmp_path: Path) -> None:
    report_path = tmp_path / "market.json"
    _write_market_report(report_path)
    cache = _write_profile_reference_cache(tmp_path / "funds.sqlite")

    index = FundExplorerIndex(report_path, catalog_cache=cache)

    catalog_only = index.search(FundSearchQuery(q="创新药"))
    overlap = index.get("510300")

    assert [item["code"] for item in catalog_only["items"]] == ["021511"]
    assert catalog_only["items"][0]["purchase_status"] == "开放申购"
    assert overlap is not None
    assert overlap["name"] == "目录版沪深300ETF"
    assert overlap["fund_type"] == "ETF-指数型"
    assert overlap["nav"] == 4.21
    assert overlap["themes"] == ["宽基", "沪深300"]
    assert index.search(FundSearchQuery())["total"] == 4


def test_search_filters_and_facets_purchase_status(tmp_path: Path) -> None:
    report_path = tmp_path / "market.json"
    _write_market_report(report_path)
    cache = _write_profile_reference_cache(tmp_path / "funds.sqlite")

    result = FundExplorerIndex(report_path, catalog_cache=cache).search(
        FundSearchQuery(purchase_status="开放申购")
    )

    assert [item["code"] for item in result["items"]] == ["021511"]
    assert result["facets"]["purchase_statuses"] == {"开放申购": 1}


def test_catalog_index_hot_reloads_and_keeps_last_good_on_cache_error(tmp_path: Path) -> None:
    report_path = tmp_path / "market.json"
    _write_market_report(report_path)
    cache = _write_profile_reference_cache(tmp_path / "funds.sqlite")
    index = FundExplorerIndex(report_path, catalog_cache=cache)
    assert index.search(FundSearchQuery(q="021511"))["total"] == 1

    cache.replace_fund_catalog_snapshot(
        [
            FundCatalogEntry(
                code="021580",
                name="创新药混合C",
                fund_type="混合型",
                source="akshare",
            )
        ],
        snapshot_id="catalog-v2",
        as_of="2026-07-22",
        ttl_days=30,
        now=datetime(2026, 7, 22, 14, 0, tzinfo=timezone.utc),
    )
    stat = cache.path.stat()
    os.utime(cache.path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))

    reloaded = index.search(FundSearchQuery(q="021580"))
    assert reloaded["total"] == 1
    assert index.load_count == 2

    cache.path.write_bytes(b"not-a-sqlite-database")
    failed = index.search(FundSearchQuery(q="021580"))

    assert failed["total"] == 1
    assert failed["index_stale"] is True
    assert failed["warnings"] == ["fund_explorer_index_reload_failed:DatabaseError"]


def test_search_sorts_paginates_and_returns_facets(tmp_path: Path) -> None:
    report_path = tmp_path / "market.json"
    _write_market_report(report_path)
    index = FundExplorerIndex(report_path)

    result = index.search(
        FundSearchQuery(sort="return_1m", direction="desc", page=1, page_size=1)
    )

    assert result["total"] == 3
    assert result["total_pages"] == 3
    assert [item["code"] for item in result["items"]] == ["510300"]
    assert result["facets"]["fund_types"] == {"ETF": 1, "unknown": 1, "混合型": 1}
    assert result["facets"]["exchange_traded"] == {"true": 1, "false": 2}
    assert result["as_of"] == "2026-07-21"
    assert result["source"] == "akshare"
    assert result["data_quality_grade"] == "warning"


def test_search_validates_page_boundaries(tmp_path: Path) -> None:
    report_path = tmp_path / "market.json"
    _write_market_report(report_path)
    index = FundExplorerIndex(report_path)

    with pytest.raises(ValueError, match="page"):
        index.search(FundSearchQuery(page=0))
    with pytest.raises(ValueError, match="page_size"):
        index.search(FundSearchQuery(page_size=101))


def test_index_reloads_changed_file_and_keeps_last_good_data_on_error(tmp_path: Path) -> None:
    report_path = tmp_path / "market.json"
    _write_market_report(report_path)
    index = FundExplorerIndex(report_path)
    first = index.search(FundSearchQuery(q="510300"))
    assert first["total"] == 1
    assert index.load_count == 1

    unchanged = index.search(FundSearchQuery(q="510300"))
    assert unchanged["total"] == 1
    assert index.load_count == 1

    report_path.write_text("{invalid", encoding="utf-8")
    fallback = index.search(FundSearchQuery(q="510300"))

    assert fallback["total"] == 1
    assert fallback["index_stale"] is True
    assert fallback["warnings"] == ["fund_explorer_index_reload_failed:JSONDecodeError"]
    assert index.load_count == 1


def test_missing_report_returns_empty_unavailable_result(tmp_path: Path) -> None:
    index = FundExplorerIndex(tmp_path / "missing.json")

    result = index.search(FundSearchQuery())

    assert result["items"] == []
    assert result["total"] == 0
    assert result["availability"] == "missing"
    assert result["warnings"] == ["fund_explorer_source_missing"]


def test_get_fund_returns_allowed_detail_or_none(tmp_path: Path) -> None:
    report_path = tmp_path / "market.json"
    _write_market_report(report_path)
    index = FundExplorerIndex(report_path)

    assert index.get("SH510300")["code"] == "510300"
    assert index.get("999999") is None
