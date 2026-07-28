from pathlib import Path
import json
from dataclasses import asdict

from fastapi.testclient import TestClient

from fund_agent import __version__
from fund_agent.market_history import MarketHistoryUnavailable
from fund_agent.models import ResearchAnswer
from fund_agent.sector_history import MarketSectorUnavailable
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


def test_local_api_rejects_untrusted_host_and_cross_origin_write(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(output_dir / "manual_review_queue.json", [{"review_id": "r1", "signal_id": "s1"}])
    client = TestClient(create_web_app(output_dir=output_dir))

    untrusted_host = client.get("/api/health", headers={"host": "attacker.example:8765"})
    cross_origin = client.post(
        "/api/reviews/r1",
        headers={"origin": "https://attacker.example"},
        json={"status": "needs_more_data", "signal_id": "s1"},
    )
    local_origin = client.post(
        "/api/reviews/r1",
        headers={"origin": "http://127.0.0.1:8765"},
        json={"status": "needs_more_data", "signal_id": "s1"},
    )

    assert untrusted_host.status_code == 400
    assert cross_origin.status_code == 403
    assert local_origin.status_code == 200


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


def test_product_api_projects_user_fields_without_provider_or_warning_codes(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(
        output_dir / "market" / "market_intelligence_report.json",
        {
            "as_of": "2026-07-27",
            "total_funds": 21600,
            "total_etfs": 3500,
            "source": "cache:akshare",
            "data_quality_summary": {"grade": "warning"},
            "records": [
                {
                    "code": "510300",
                    "name": "沪深300ETF",
                    "fund_type": "ETF",
                    "nav": 4.2,
                    "source": "cache:akshare",
                    "as_of": "2026-07-27",
                    "metadata": {"returns": {"1m": 2.5}, "stale": True},
                }
            ],
        },
    )
    _write_json(
        output_dir / "fund_details" / "watchlist_fund_details.json",
        {
            "as_of": "2026-07-27",
            "fund_details": [
                {
                    "code": "510300",
                    "name": "沪深300ETF",
                    "fund_company": "示例基金公司",
                    "missing_fields": ["rating"],
                    "source": "cache:akshare",
                }
            ],
        },
    )
    _write_json(
        output_dir / "portfolio" / "portfolio_report.json",
        {
            "as_of": "2026-07-27",
            "portfolio_name": "我的组合",
            "holding_count": 1,
            "valuation_status": "unavailable",
            "total_value": None,
            "positions": [{"code": "510300", "name": "沪深300ETF", "current_value": None, "source": "cache:akshare"}],
            "warnings": ["portfolio_current_value_unavailable"],
        },
    )
    client = TestClient(create_web_app(output_dir=output_dir))

    market = client.get("/api/product/market")
    search = client.get("/api/product/funds/search")
    detail = client.get("/api/product/funds/510300")
    watchlist = client.get("/api/product/watchlist")
    portfolio = client.get("/api/product/portfolio")

    assert market.status_code == 200
    assert search.status_code == 200
    assert detail.status_code == 200
    assert watchlist.status_code == 200
    assert portfolio.status_code == 200
    assert market.json()["data"]["data_status"]["label"] == "请留意数据日期"
    assert search.json()["items"][0]["data_status"]["state"] == "attention"
    assert detail.json()["fund"]["code"] == "510300"
    assert watchlist.json()["data"]["funds"][0]["code"] == "510300"
    assert portfolio.json()["data"]["valuation"]["label"] == "当前估值暂不可用"
    for response in (market, search, detail, watchlist, portfolio):
        _assert_product_payload_has_no_diagnostics(response.json())


def test_product_market_subresources_hide_diagnostics_and_return_empty_state_when_unavailable(tmp_path):
    class HistoryService:
        def get_index_history(self, symbol, *, window):
            assert (symbol, window) == ("000300", "6m")
            return {
                "symbol": symbol,
                "name": "沪深300",
                "range": window,
                "point_count": 1,
                "points": [{"date": "2026-07-27", "close": 4702.43, "source": "cache:akshare"}],
                "source": "cache:akshare",
                "as_of": "2026-07-27",
                "stale": True,
                "fallback_used": True,
                "data_quality_grade": "warning",
            }

    class SectorService:
        def search_sectors(self, *, q, page, page_size):
            assert (q, page, page_size) == ("医药", 1, 12)
            return {
                "items": [{"symbol": "BK1607", "name": "医药流通", "latest": 1961.48, "source": "akshare"}],
                "page": page,
                "page_size": page_size,
                "total": 1,
                "total_pages": 1,
                "query": q,
                "source": "akshare",
                "as_of": "2026-07-27",
                "data_quality_grade": "normal",
            }

        def get_sector_history(self, symbol, *, window):
            raise MarketSectorUnavailable("not available for test")

    client = TestClient(
        create_web_app(
            output_dir=tmp_path / "outputs",
            market_history_service=HistoryService(),
            market_sector_service=SectorService(),
        )
    )

    index = client.get("/api/product/market/indices/000300/history", params={"range": "6m"})
    sectors = client.get("/api/product/market/sectors", params={"q": "医药", "page": 1, "page_size": 12})
    unavailable = client.get("/api/product/market/sectors/BK1607/history", params={"range": "6m"})

    assert index.status_code == 200
    assert sectors.status_code == 200
    assert unavailable.status_code == 200
    assert index.json()["data_status"]["label"] == "请留意数据日期"
    assert sectors.json()["items"][0]["name"] == "医药流通"
    assert unavailable.json()["availability"] == "missing"
    assert unavailable.json()["data_status"]["label"] == "暂未获取到数据"
    for payload in (index.json(), sectors.json(), unavailable.json()):
        _assert_product_payload_has_no_diagnostics(payload)


def test_news_api_marks_only_related_codes_present_in_the_local_fund_index(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(
        output_dir / "market" / "market_intelligence_report.json",
        {
            "records": [
                {
                    "code": "510300",
                    "name": "沪深300ETF",
                    "metadata": {},
                }
            ]
        },
    )
    _write_json(
        output_dir / "news" / "news_evidence_report.json",
        {
            "items": [
                {"title": "已索引", "related_funds": ["510300", "SH510300"]},
                {"title": "索引外", "related_funds": ["999999", "not-a-code"]},
            ]
        },
    )

    data = TestClient(create_web_app(output_dir=output_dir)).get("/api/news").json()["data"]

    assert data["indexed_fund_codes"] == ["510300"]
    assert data["items"][1]["related_funds"] == ["999999", "not-a-code"]


def test_missing_research_payloads_are_explicit_and_non_fatal(tmp_path):
    client = TestClient(create_web_app(output_dir=tmp_path / "outputs"))

    for endpoint in ("market", "funds", "portfolio", "news"):
        response = client.get(f"/api/{endpoint}")
        assert response.status_code == 200
        assert response.json()["availability"] == "missing"
        assert response.json()["data"] in ({}, {"details": {}, "signal_candidates": {}}, {"intelligence": {}, "trend": {}})


def _assert_product_payload_has_no_diagnostics(value):
    forbidden = {
        "source",
        "updated_at",
        "expires_at",
        "stale",
        "fallback_used",
        "fallback_reason",
        "data_quality_grade",
        "warnings",
        "schema_version",
        "metadata",
    }
    if isinstance(value, dict):
        assert not (set(value) & forbidden)
        for child in value.values():
            _assert_product_payload_has_no_diagnostics(child)
    elif isinstance(value, list):
        for child in value:
            _assert_product_payload_has_no_diagnostics(child)


def test_read_api_normalizes_non_object_json_roots(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(output_dir / "market" / "market_intelligence_report.json", None)
    _write_json(output_dir / "market" / "market_trend_report.json", ["legacy"])
    _write_json(output_dir / "fund_details" / "watchlist_fund_details.json", None)
    _write_json(output_dir / "signal_candidates.json", ["legacy"])
    _write_json(output_dir / "portfolio" / "portfolio_report.json", None)
    _write_json(output_dir / "news" / "news_evidence_report.json", ["legacy"])
    client = TestClient(create_web_app(output_dir=output_dir))

    assert client.get("/api/market").json()["data"] == {"intelligence": {}, "trend": {}}
    assert client.get("/api/funds").json()["data"] == {"details": {}, "signal_candidates": {}}
    assert client.get("/api/portfolio").json()["data"] == {}
    assert client.get("/api/news").json()["data"] == {}


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


def test_copilot_api_returns_structured_answer_and_citations(monkeypatch, tmp_path):
    output_dir = tmp_path / "outputs"
    answer = ResearchAnswer(
        schema_version="1.0",
        generated_at="2026-07-16T10:00:00+00:00",
        generator="ya-fundmind/2.0.0rc1",
        question="市场热点是什么？",
        intent={"intent": "market_overview"},
        answer_status="answered",
        as_of="2026-07-16",
        summary="人工智能主题热度较高，但仍需人工审核。",
        findings=(
            {
                "finding_id": "f1",
                "label": "人工智能主题",
                "value": "热度上升",
                "evidence_ids": ["e1"],
                "quality_grade": "normal",
            },
        ),
        evidence=(
            {
                "evidence_id": "e1",
                "source": "market_intelligence",
                "as_of": "2026-07-16",
                "quality_grade": "normal",
                "stale": False,
            },
        ),
        data_gaps=(),
        warnings=(),
        review_required=True,
        confidence="medium",
    )
    calls = []

    def fake_run(*, question, output_dir):
        calls.append((question, output_dir))
        return answer

    monkeypatch.setattr("fund_agent.web_api.run_copilot_for_web", fake_run)
    client = TestClient(create_web_app(output_dir=output_dir))

    response = client.post("/api/copilot/ask", json={"question": "  市场热点是什么？  "})

    assert response.status_code == 200
    payload = response.json()["data"]
    expected_answer = json.loads(json.dumps(asdict(answer), ensure_ascii=False))
    assert payload["answer"] == expected_answer
    assert payload["view_model"]["findings"][0]["citations"][0]["evidence_id"] == "e1"
    assert calls == [("市场热点是什么？", output_dir.resolve())]


def test_copilot_api_rejects_blank_or_oversized_question(tmp_path):
    client = TestClient(create_web_app(output_dir=tmp_path / "outputs"))

    blank = client.post("/api/copilot/ask", json={"question": "   "})
    oversized = client.post("/api/copilot/ask", json={"question": "x" * 1001})

    assert blank.status_code == 422
    assert blank.json()["detail"]["code"] == "invalid_question"
    assert oversized.status_code == 422


def test_review_api_lists_and_updates_existing_review_item(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(output_dir / "manual_review_queue.json", [{"review_id": "r1", "signal_id": "s1"}])
    _write_json(output_dir / "manual_review_state.json", {"items": []})
    client = TestClient(create_web_app(output_dir=output_dir))

    listed = client.get("/api/reviews")
    updated = client.post(
        "/api/reviews/r1",
        json={
            "status": "needs_more_data",
            "note": "等待更多有效运行日",
            "reviewer": "local",
            "signal_id": "s1",
        },
    )

    assert listed.status_code == 200
    assert listed.json()["data"]["queue"][0]["review_id"] == "r1"
    assert updated.status_code == 200
    assert updated.json()["data"]["status"] == "needs_more_data"
    saved = json.loads((output_dir / "manual_review_state.json").read_text(encoding="utf-8"))
    assert saved["items"][0]["review_id"] == "r1"


def test_review_api_rejects_unknown_item_and_invalid_status(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(output_dir / "manual_review_queue.json", [{"review_id": "r1"}])
    client = TestClient(create_web_app(output_dir=output_dir))

    missing = client.post("/api/reviews/unknown", json={"status": "needs_more_data"})
    invalid = client.post("/api/reviews/r1", json={"status": "buy_now"})

    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "review_not_found"
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "invalid_review_status"


def test_review_api_rejects_signal_id_rebinding(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(output_dir / "manual_review_queue.json", [{"review_id": "r1", "signal_id": "canonical-signal"}])
    client = TestClient(create_web_app(output_dir=output_dir))

    response = client.post(
        "/api/reviews/r1",
        json={"status": "needs_more_data", "signal_id": "forged-signal"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "review_signal_mismatch"
    assert not (output_dir / "manual_review_state.json").exists()


def test_report_download_uses_allowlist(tmp_path):
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    (output_dir / "fund_agent_report.html").write_text("<h1>Fund report</h1>", encoding="utf-8")
    (output_dir / "secret.txt").write_text("secret", encoding="utf-8")
    client = TestClient(create_web_app(output_dir=output_dir))

    available = client.get("/api/reports/fund_agent_report")
    unknown = client.get("/api/reports/secret")
    missing = client.get("/api/reports/news")

    assert available.status_code == 200
    assert "Fund report" in available.text
    assert unknown.status_code == 404
    assert unknown.json()["detail"]["code"] == "report_not_allowed"
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "report_missing"


def test_spa_fallback_serves_index_without_masking_api_routes(tmp_path):
    output_dir = tmp_path / "outputs"
    static_dir = tmp_path / "dist"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<!doctype html><title>Product console</title>", encoding="utf-8")
    (static_dir / "app.js").write_text("window.ready=true", encoding="utf-8")
    client = TestClient(create_web_app(output_dir=output_dir, static_dir=static_dir))

    route = client.get("/market")
    asset = client.get("/app.js")
    missing_api = client.get("/api/not-a-route")

    assert route.status_code == 200
    assert "Product console" in route.text
    assert asset.status_code == 200
    assert "window.ready=true" in asset.text
    assert missing_api.status_code == 404
    assert "Product console" not in missing_api.text
