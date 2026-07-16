from pathlib import Path
import json

from fastapi.testclient import TestClient

from fund_agent import __version__
from fund_agent.web_api import create_web_app


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_health_reports_local_readiness_and_fixed_output_dir(tmp_path):
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    app = create_web_app(output_dir=output_dir)

    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "generator": f"ya-fundmind/{__version__}",
        "local_only": True,
        "output_status": "available",
        "not_production_model": True,
        "main_score_changed": False,
        "main_risk_changed": False,
    }
    assert app.state.output_dir == output_dir.resolve()


def test_health_starts_when_output_dir_is_missing(tmp_path):
    output_dir = tmp_path / "missing"
    app = create_web_app(output_dir=output_dir)

    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["output_status"] == "missing_outputs"
    assert app.state.output_dir == output_dir.resolve()


def test_app_uses_explicit_review_state_path(tmp_path):
    output_dir = tmp_path / "outputs"
    review_state = tmp_path / "review" / "state.json"

    app = create_web_app(output_dir=output_dir, review_state_path=review_state)

    assert app.state.review_state_path == Path(review_state).resolve()


def test_read_api_exposes_structured_research_payloads(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(output_dir / "daily_research_summary.json", {"as_of": "2026-07-16", "status": "success"})
    _write_json(output_dir / "latest_summary.json", {"daily": {"status": "success"}})
    _write_json(output_dir / "manual_review_queue.json", [{"review_id": "r1"}])
    _write_json(output_dir / "manual_review_state.json", {"items": []})
    _write_json(output_dir / "market" / "market_intelligence_report.json", {"themes": [{"name": "AI"}]})
    _write_json(output_dir / "market" / "market_trend_report.json", {"trend_items": [{"theme": "AI"}]})
    _write_json(output_dir / "fund_details" / "watchlist_fund_details.json", {"funds": [{"code": "000001"}]})
    _write_json(output_dir / "signal_candidates.json", {"eligible_signals": [{"code": "000001"}]})
    _write_json(output_dir / "portfolio" / "portfolio_report.json", {"positions": [{"code": "000001"}]})
    _write_json(output_dir / "news" / "news_evidence_report.json", {"evidence": [{"title": "政策"}]})
    app = create_web_app(output_dir=output_dir)
    client = TestClient(app)

    overview = client.get("/api/overview").json()
    assert overview["availability"] == "available"
    assert overview["data"]["review_queue_count"] == 1
    assert overview["data"]["not_production_model"] is True

    market = client.get("/api/market").json()
    assert market["availability"] == "available"
    assert market["data"]["intelligence"]["themes"][0]["name"] == "AI"
    assert market["data"]["trend"]["trend_items"][0]["theme"] == "AI"

    funds = client.get("/api/funds").json()
    assert funds["data"]["details"]["funds"][0]["code"] == "000001"
    assert funds["data"]["signal_candidates"]["eligible_signals"][0]["code"] == "000001"

    assert client.get("/api/portfolio").json()["data"]["positions"][0]["code"] == "000001"
    assert client.get("/api/news").json()["data"]["evidence"][0]["title"] == "政策"


def test_missing_research_payloads_are_explicit_and_non_fatal(tmp_path):
    client = TestClient(create_web_app(output_dir=tmp_path / "outputs"))

    for endpoint in ("market", "funds", "portfolio", "news"):
        response = client.get(f"/api/{endpoint}")
        assert response.status_code == 200
        assert response.json()["availability"] == "missing"
        assert response.json()["data"] in ({}, {"details": {}, "signal_candidates": {}}, {"intelligence": {}, "trend": {}})


def test_reports_api_uses_fixed_allowlist_and_safe_relative_paths(tmp_path):
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    (output_dir / "latest_summary.md").write_text("# latest", encoding="utf-8")
    (output_dir / "secret.txt").write_text("do not expose", encoding="utf-8")
    client = TestClient(create_web_app(output_dir=output_dir))

    response = client.get("/api/reports")

    assert response.status_code == 200
    reports = response.json()["data"]["reports"]
    assert {item["report_id"] for item in reports} == {
        "latest_summary",
        "fund_agent_report",
        "dashboard",
        "market",
        "funds",
        "portfolio",
        "news",
        "review",
    }
    latest = next(item for item in reports if item["report_id"] == "latest_summary")
    assert latest["relative_path"] == "latest_summary.md"
    assert latest["exists"] is True
    serialized = response.text
    assert str(output_dir) not in serialized
    assert "secret.txt" not in serialized


def test_read_api_does_not_accept_path_override(tmp_path):
    output_dir = tmp_path / "outputs"
    outside = tmp_path / "outside"
    _write_json(outside / "market" / "market_intelligence_report.json", {"secret": True})
    client = TestClient(create_web_app(output_dir=output_dir))

    response = client.get("/api/market", params={"output_dir": str(outside), "path": "../outside"})

    assert response.status_code == 200
    assert response.json()["availability"] == "missing"
    assert "secret" not in response.text
