from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from fund_agent.cache import FundCache
from fund_agent.fund_history import FundHistoryUnavailable
from fund_agent.models import FundCatalogEntry, FundTradingRule
from fund_agent.web_api import _build_fund_history_service, create_web_app


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_market(output_dir: Path) -> None:
    _write_json(
        output_dir / "market" / "market_intelligence_report.json",
        {
            "as_of": "2026-07-21",
            "source": "akshare",
            "data_quality_summary": {"grade": "normal"},
            "records": [
                {
                    "code": "510300",
                    "name": "沪深300ETF华泰柏瑞",
                    "fund_type": "ETF",
                    "exchange_traded": True,
                    "nav": 4.21,
                    "source": "akshare",
                    "as_of": "2026-07-21",
                    "metadata": {"returns": {"1m": 2.5}, "stale": False},
                },
                {
                    "code": "000001",
                    "name": "华夏成长混合",
                    "fund_type": "混合型",
                    "exchange_traded": False,
                    "source": "akshare",
                    "as_of": "2026-07-21",
                    "metadata": {"returns": {"1m": -1.2}, "stale": False},
                },
            ],
            "classifications": [
                {"code": "510300", "primary_theme": "宽基", "themes": ["宽基"]},
                {"code": "000001", "primary_theme": "成长", "themes": ["成长"]},
            ],
        },
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
            FundTradingRule(code="510300", purchase_status="场内交易", source="akshare"),
            FundTradingRule(code="021511", purchase_status="开放申购", source="akshare"),
        ],
        snapshot_id="purchase-v1",
        as_of="2026-07-21",
        ttl_days=30,
        now=now,
    )
    return cache


def test_search_api_supports_query_filters_and_pagination(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    _write_market(output_dir)
    client = TestClient(create_web_app(output_dir=output_dir))

    response = client.get(
        "/api/funds/search",
        params={
            "q": "ETF",
            "fund_type": "ETF",
            "theme": "宽基",
            "exchange_traded": "true",
            "sort": "return_1m",
            "direction": "desc",
            "page": 1,
            "page_size": 25,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["code"] == "510300"
    assert payload["facets"]["themes"] == {"宽基": 1}
    assert payload["as_of"] == "2026-07-21"
    assert payload["source"] == "akshare"


def test_search_api_validates_parameters(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    _write_market(output_dir)
    client = TestClient(create_web_app(output_dir=output_dir))

    assert client.get("/api/funds/search", params={"page": 0}).status_code == 422
    assert client.get("/api/funds/search", params={"page_size": 101}).status_code == 422
    assert client.get("/api/funds/search", params={"sort": "secret"}).status_code == 422
    assert client.get("/api/funds/search", params={"quality": "perfect"}).status_code == 422


def test_product_search_uses_catalog_union_and_purchase_status(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    _write_market(output_dir)
    cache = _write_profile_reference_cache(tmp_path / "funds.sqlite")
    client = TestClient(
        create_web_app(output_dir=output_dir, fund_catalog_cache=cache)
    )

    response = client.get(
        "/api/product/funds/search",
        params={"purchase_status": "开放申购"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["code"] == "021511"
    assert payload["items"][0]["purchase_status"] == "开放申购"
    assert payload["facets"]["purchase_statuses"] == {"开放申购": 1}
    assert "source" not in payload["items"][0]
    assert "catalog_sources" not in response.text


def test_fund_detail_api_merges_safe_research_detail(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    _write_market(output_dir)
    _write_json(
        output_dir / "fund_details" / "watchlist_fund_details.json",
        {
            "fund_details": [
                {
                    "code": "510300",
                    "fund_company": "华泰柏瑞基金",
                    "fund_manager": "示例经理",
                    "return_windows": {"1m": {"total_return": 2.5}},
                    "missing_fields": ["rating"],
                    "latest_detail_json_path": "/private/secret/fund.json",
                }
            ]
        },
    )
    client = TestClient(create_web_app(output_dir=output_dir))

    response = client.get("/api/funds/510300")

    assert response.status_code == 200
    payload = response.json()
    assert payload["fund"]["name"] == "沪深300ETF华泰柏瑞"
    assert payload["research_detail"]["fund_company"] == "华泰柏瑞基金"
    assert payload["research_detail"]["return_windows"]["1m"]["total_return"] == 2.5
    assert "latest_detail_json_path" not in response.text
    assert "/private/secret" not in response.text
    assert payload["not_production_model"] is True
    assert payload["main_score_changed"] is False
    assert payload["main_risk_changed"] is False


def test_fund_detail_api_rejects_invalid_or_missing_code(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    _write_market(output_dir)
    client = TestClient(create_web_app(output_dir=output_dir))

    invalid = client.get("/api/funds/not-a-code")
    missing = client.get("/api/funds/999999")

    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "invalid_fund_code"
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "fund_not_found"


def test_search_route_is_not_shadowed_by_fund_code_route(tmp_path: Path) -> None:
    client = TestClient(create_web_app(output_dir=tmp_path / "outputs"))

    response = client.get("/api/funds/search")

    assert response.status_code == 200
    assert response.json()["availability"] == "missing"


def test_existing_watchlist_funds_api_remains_compatible(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    _write_json(
        output_dir / "fund_details" / "watchlist_fund_details.json",
        {"fund_details": [{"code": "510300"}]},
    )
    client = TestClient(create_web_app(output_dir=output_dir))

    response = client.get("/api/funds")

    assert response.status_code == 200
    assert response.json()["data"]["details"]["fund_details"][0]["code"] == "510300"


class StubHistoryService:
    def __init__(self):
        self.calls = []

    def get_history(self, code: str, *, window: str):
        self.calls.append((code, window))
        return {
            "code": code,
            "range": window,
            "point_count": 2,
            "points": [
                {
                    "date": "2026-07-20",
                    "unit_nav": 4.1,
                    "accumulated_nav": 4.1,
                    "daily_return": 0.2,
                    "source": "cache:akshare",
                },
                {
                    "date": "2026-07-21",
                    "unit_nav": 4.2,
                    "accumulated_nav": 4.2,
                    "daily_return": 2.44,
                    "source": "cache:akshare",
                },
            ],
            "source": "cache:akshare",
            "as_of": "2026-07-21",
            "updated_at": "2026-07-21T10:00:00+00:00",
            "expires_at": "2026-07-22T10:00:00+00:00",
            "stale": False,
            "fallback_used": False,
            "data_quality_grade": "warning",
            "warnings": [],
            "not_production_model": True,
            "main_score_changed": False,
            "main_risk_changed": False,
        }


def test_fund_history_api_returns_structured_nav_series(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    _write_market(output_dir)
    service = StubHistoryService()
    client = TestClient(
        create_web_app(
            output_dir=output_dir,
            fund_history_service=service,
        )
    )

    response = client.get("/api/funds/510300/history", params={"range": "3m"})

    assert response.status_code == 200
    assert service.calls == [("510300", "3m")]
    payload = response.json()
    assert payload["code"] == "510300"
    assert payload["range"] == "3m"
    assert payload["points"][-1]["unit_nav"] == 4.2
    assert payload["source"] == "cache:akshare"
    assert payload["not_production_model"] is True


def test_fund_history_api_validates_code_window_and_market_membership(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    _write_market(output_dir)
    client = TestClient(
        create_web_app(
            output_dir=output_dir,
            fund_history_service=StubHistoryService(),
        )
    )

    assert client.get("/api/funds/not-code/history").status_code == 422
    assert client.get("/api/funds/510300/history", params={"range": "2y"}).status_code == 422
    missing = client.get("/api/funds/999999/history")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "fund_not_found"


class UnavailableHistoryService:
    def get_history(self, code: str, *, window: str):
        raise FundHistoryUnavailable("history endpoint down")


def test_fund_history_api_returns_explainable_503(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    _write_market(output_dir)
    client = TestClient(
        create_web_app(
            output_dir=output_dir,
            fund_history_service=UnavailableHistoryService(),
        )
    )

    response = client.get("/api/funds/510300/history")

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "fund_history_unavailable",
        "message": "history endpoint down",
    }


def test_fund_history_service_resolves_cache_from_project_root(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "external" / "nested" / "outputs"

    service = _build_fund_history_service(
        output_dir,
        project_root=project_root,
    )

    assert service.cache.path == project_root / "data" / "cache" / "funds.sqlite"
