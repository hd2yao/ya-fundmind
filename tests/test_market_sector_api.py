from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from fund_agent.sector_history import MarketSectorUnavailable
from fund_agent.web_api import create_web_app


class StubMarketSectorService:
    def __init__(self):
        self.search_calls = []
        self.history_calls = []

    def search_sectors(self, *, q, page, page_size):
        self.search_calls.append((q, page, page_size))
        return {
            "items": [
                {
                    "symbol": "BK1036",
                    "name": "半导体",
                    "entity_type": "industry",
                    "latest": 1823.4,
                    "change_pct": 2.31,
                    "source": "cache:akshare",
                    "as_of": "2026-07-23",
                    "stale": False,
                }
            ],
            "page": page,
            "page_size": page_size,
            "total": 1,
            "total_pages": 1,
            "query": q,
            "sort": "change_pct_desc",
            "source": "cache:akshare",
            "as_of": "2026-07-23",
            "stale": False,
            "fallback_used": False,
            "data_quality_grade": "normal",
            "warnings": [],
            "not_production_model": True,
            "main_score_changed": False,
            "main_risk_changed": False,
        }

    def get_sector_history(self, symbol, *, window):
        self.history_calls.append((symbol, window))
        if symbol == "BK9999":
            raise ValueError("Unknown industry symbol: BK9999")
        return {
            "symbol": symbol,
            "name": "半导体",
            "series_type": "industry",
            "range": window,
            "point_count": 1,
            "required_points": 120,
            "points": [
                {
                    "date": "2026-07-22",
                    "open": 1810.0,
                    "close": 1823.4,
                    "high": 1830.0,
                    "low": 1802.0,
                    "volume": 130000.0,
                    "turnover": 1000000000.0,
                    "turnover_rate": 2.3,
                    "change_pct": 0.74,
                    "source": "cache:akshare",
                }
            ],
            "source": "cache:akshare",
            "as_of": "2026-07-22",
            "updated_at": "2026-07-22T10:00:00+00:00",
            "expires_at": "2026-07-23T10:00:00+00:00",
            "stale": False,
            "fallback_used": False,
            "data_quality_grade": "warning",
            "warnings": [],
            "not_production_model": True,
            "main_score_changed": False,
            "main_risk_changed": False,
        }


def test_market_sector_catalog_supports_search_and_pagination(
    tmp_path: Path,
) -> None:
    service = StubMarketSectorService()
    client = TestClient(
        create_web_app(
            output_dir=tmp_path / "outputs",
            market_sector_service=service,
        )
    )

    response = client.get(
        "/api/market/sectors",
        params={"q": "半导体", "page": 2, "page_size": 10},
    )

    assert response.status_code == 200
    assert service.search_calls == [("半导体", 2, 10)]
    assert response.json()["items"][0]["symbol"] == "BK1036"


def test_market_sector_catalog_rejects_invalid_pagination(
    tmp_path: Path,
) -> None:
    client = TestClient(
        create_web_app(
            output_dir=tmp_path / "outputs",
            market_sector_service=StubMarketSectorService(),
        )
    )

    assert (
        client.get(
            "/api/market/sectors",
            params={"page_size": 101},
        ).status_code
        == 422
    )


def test_market_sector_history_returns_structured_series(
    tmp_path: Path,
) -> None:
    service = StubMarketSectorService()
    client = TestClient(
        create_web_app(
            output_dir=tmp_path / "outputs",
            market_sector_service=service,
        )
    )

    response = client.get(
        "/api/market/sectors/BK1036/history",
        params={"range": "6m"},
    )

    assert response.status_code == 200
    assert service.history_calls == [("BK1036", "6m")]
    assert response.json()["series_type"] == "industry"
    assert response.json()["points"][0]["turnover_rate"] == 2.3


def test_market_sector_history_rejects_invalid_or_unknown_symbol(
    tmp_path: Path,
) -> None:
    client = TestClient(
        create_web_app(
            output_dir=tmp_path / "outputs",
            market_sector_service=StubMarketSectorService(),
        )
    )

    invalid = client.get("/api/market/sectors/not-a-code/history")
    unknown = client.get("/api/market/sectors/BK9999/history")

    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "invalid_sector_code"
    assert unknown.status_code == 404
    assert unknown.json()["detail"]["code"] == "sector_not_found"


class UnavailableMarketSectorService:
    def search_sectors(self, **kwargs):
        raise MarketSectorUnavailable("catalog endpoint down")

    def get_sector_history(self, symbol, *, window):
        raise MarketSectorUnavailable("history endpoint down")


def test_market_sector_endpoints_return_explainable_503(
    tmp_path: Path,
) -> None:
    client = TestClient(
        create_web_app(
            output_dir=tmp_path / "outputs",
            market_sector_service=UnavailableMarketSectorService(),
        )
    )

    catalog = client.get("/api/market/sectors")
    history = client.get("/api/market/sectors/BK1036/history")

    assert catalog.status_code == 503
    assert catalog.json()["detail"]["code"] == "market_sector_unavailable"
    assert history.status_code == 503
    assert history.json()["detail"]["message"] == "history endpoint down"
