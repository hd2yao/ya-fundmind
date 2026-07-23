from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from fund_agent.market_history import MarketHistoryUnavailable
from fund_agent.web_api import create_web_app


class StubMarketHistoryService:
    def __init__(self):
        self.calls = []

    def get_index_history(self, symbol: str, *, window: str):
        self.calls.append((symbol, window))
        return {
            "symbol": symbol,
            "name": "沪深300",
            "series_type": "index",
            "range": window,
            "point_count": 2,
            "required_points": 60,
            "points": [
                {
                    "date": "2026-07-21",
                    "open": 4610.0,
                    "close": 4620.0,
                    "high": 4630.0,
                    "low": 4600.0,
                    "volume": 123456.0,
                    "turnover": 987654321.0,
                    "change_pct": 0.52,
                    "source": "cache:akshare",
                },
                {
                    "date": "2026-07-22",
                    "open": 4620.0,
                    "close": 4652.8,
                    "high": 4660.0,
                    "low": 4612.0,
                    "volume": 130000.0,
                    "turnover": 1000000000.0,
                    "change_pct": 0.71,
                    "source": "cache:akshare",
                },
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


def test_market_index_catalog_is_fixed_allowlist(tmp_path: Path) -> None:
    client = TestClient(create_web_app(output_dir=tmp_path / "outputs"))

    response = client.get("/api/market/indices")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {"symbol": "000001", "name": "上证指数"},
            {"symbol": "000300", "name": "沪深300"},
            {"symbol": "399006", "name": "创业板指"},
        ]
    }


def test_market_index_history_returns_structured_series(tmp_path: Path) -> None:
    service = StubMarketHistoryService()
    client = TestClient(
        create_web_app(
            output_dir=tmp_path / "outputs",
            market_history_service=service,
        )
    )

    response = client.get(
        "/api/market/indices/000300/history",
        params={"range": "3m"},
    )

    assert response.status_code == 200
    assert service.calls == [("000300", "3m")]
    payload = response.json()
    assert payload["name"] == "沪深300"
    assert payload["points"][-1]["close"] == 4652.8
    assert payload["source"] == "cache:akshare"


def test_market_index_history_rejects_unknown_symbol_and_window(
    tmp_path: Path,
) -> None:
    client = TestClient(
        create_web_app(
            output_dir=tmp_path / "outputs",
            market_history_service=StubMarketHistoryService(),
        )
    )

    missing = client.get("/api/market/indices/123456/history")

    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "index_not_found"
    assert (
        client.get(
            "/api/market/indices/000300/history",
            params={"range": "2y"},
        ).status_code
        == 422
    )


class UnavailableMarketHistoryService:
    def get_index_history(self, symbol: str, *, window: str):
        raise MarketHistoryUnavailable("index endpoint down")


def test_market_index_history_returns_explainable_503(tmp_path: Path) -> None:
    client = TestClient(
        create_web_app(
            output_dir=tmp_path / "outputs",
            market_history_service=UnavailableMarketHistoryService(),
        )
    )

    response = client.get("/api/market/indices/000300/history")

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "market_history_unavailable",
        "message": "index endpoint down",
    }
