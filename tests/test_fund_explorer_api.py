from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from fund_agent.web_api import create_web_app


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
