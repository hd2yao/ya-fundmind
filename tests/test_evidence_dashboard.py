import json

from fund_agent.evidence_dashboard import generate_evidence_dashboard


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_generate_evidence_dashboard_writes_static_pages_from_json_only(tmp_path):
    runs_dir = tmp_path / "runs"
    _write_json(
        runs_dir / "2026-06-23" / "daily_research_summary.json",
        {
            "as_of": "2026-06-23",
            "status": "success",
            "data_quality_grade": "normal",
            "signal_candidates": {"eligible_count": 1, "excluded_count": 2, "display_only_count": 1},
            "experiment_scoring": {"applied_signal_count": 0, "top_exclusion_reasons": {"missing": 2}},
            "readiness_review": {"needs_more_data_count": 1},
            "missing_artifacts": [],
        },
    )
    _write_json(
        runs_dir / "2026-06-23" / "manual_review_queue.json",
        [{"review_id": "r1", "signal_id": "tiantian:return", "recommended_status": "needs_data"}],
    )
    review_state = tmp_path / "manual_review_state.json"
    _write_json(
        review_state,
        {"items": [{"review_id": "r1", "signal_id": "tiantian:return", "status": "needs_more_data"}]},
    )

    manifest_path = generate_evidence_dashboard(
        runs_dir=runs_dir,
        review_state_path=review_state,
        output_dir=tmp_path / "dashboard",
        days=30,
    )

    dashboard = tmp_path / "dashboard"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for page in ["index.html", "runs.html", "signals.html", "review.html", "data_quality.html", "market.html", "funds.html"]:
        html = (dashboard / page).read_text(encoding="utf-8")
        assert "not_production_model=true" in html
        assert "买入" not in html
        assert "卖出" not in html
    index_html = (dashboard / "index.html").read_text(encoding="utf-8")
    assert "research_loop_ready" in index_html
    assert "dashboard_ready" in index_html
    assert "market.html" in index_html
    assert "funds.html" in index_html
    assert "insufficient_history 只影响主评分/主风险接入" in index_html
    assert "当前系统可继续运行" in index_html
    market_html = (dashboard / "market.html").read_text(encoding="utf-8")
    assert "Market Intelligence 尚未运行" in market_html
    assert "Market Trend 尚未运行" in market_html
    funds_html = (dashboard / "funds.html").read_text(encoding="utf-8")
    assert "Fund Detail 尚未运行" in funds_html
    assert set(manifest["pages"]) == {
        "data_quality.html",
        "funds.html",
        "index.html",
        "market.html",
        "review.html",
        "runs.html",
        "signals.html",
    }


def test_generate_evidence_dashboard_renders_market_page_from_json(tmp_path):
    runs_dir = tmp_path / "runs"
    _write_json(
        runs_dir / "2026-06-23" / "daily_research_summary.json",
        {"as_of": "2026-06-23", "status": "success"},
    )
    _write_json(
        runs_dir / "2026-06-23" / "market_intelligence_report.json",
        {
            "as_of": "2026-06-23",
            "source": "fixture",
            "total_funds": 6,
            "total_etfs": 2,
            "themes": [{"theme": "沪深300", "sample_size": 5}],
            "hot_theme_candidates": [{"theme": "沪深300", "avg_return_1m": 3.2}],
            "insufficient_sample_themes": [{"theme": "白酒", "sample_size": 1}],
            "data_quality_summary": {"grade": "warning"},
            "warnings": ["missing 1y return window"],
            "not_production_model": True,
        },
    )
    _write_json(
        tmp_path / "market" / "market_trend_report.json",
        {
            "schema_version": "1.0",
            "generated_at": "2026-06-23T00:00:00+00:00",
            "period_days": 30,
            "snapshots_processed": 1,
            "minimum_required_snapshots": 3,
            "enough_market_history": False,
            "source": "fixture",
            "latest_as_of": "2026-06-23",
            "theme_trends": [{"theme": "沪深300", "latest_rank": 1, "rank_change": None}],
            "rising_themes": [],
            "falling_themes": [],
            "persistent_hot_themes": [{"theme": "沪深300", "hot_days": 1, "hot_ratio": 1.0}],
            "new_hot_themes": [],
            "disappeared_hot_themes": [],
            "insufficient_history_themes": [{"theme": "沪深300"}],
            "data_quality_trend": [{"as_of": "2026-06-23", "data_quality_grade": "warning"}],
            "warnings": ["insufficient_market_history"],
            "not_production_model": True,
        },
    )
    review_state = tmp_path / "manual_review_state.json"
    _write_json(review_state, {"items": []})

    generate_evidence_dashboard(
        runs_dir=runs_dir,
        review_state_path=review_state,
        output_dir=tmp_path / "dashboard",
        days=30,
    )

    market_html = (tmp_path / "dashboard" / "market.html").read_text(encoding="utf-8")
    assert "Market Intelligence" in market_html
    assert "Market Trend Summary" in market_html
    assert "snapshots_processed: 1" in market_html
    assert "趋势样本不足，但 Market Intelligence 可继续运行" in market_html
    assert "沪深300" in market_html
    assert "白酒" in market_html
    assert "not_production_model=true" in market_html
    assert "买入" not in market_html
    assert "卖出" not in market_html


def test_generate_evidence_dashboard_renders_funds_page_from_fund_details(tmp_path):
    runs_dir = tmp_path / "runs"
    _write_json(
        runs_dir / "2026-06-23" / "daily_research_summary.json",
        {"as_of": "2026-06-23", "status": "success"},
    )
    _write_json(
        tmp_path / "fund_details" / "watchlist_fund_details.json",
        {
            "as_of": "2026-06-23",
            "detail_count": 1,
            "fund_details": [
                {
                    "code": "021511",
                    "name": "宏利半导体产业混合发起C",
                    "fund_type": "混合型",
                    "primary_theme": "半导体",
                    "themes": ["半导体"],
                    "data_quality_grade": "warning",
                    "unknown_reason": "",
                    "data_coverage": {"status": "partial", "coverage_ratio": 0.75},
                    "peer_comparison": {"peer_sample_size": 2, "sample_status": "sufficient", "rank_by_1m_return": 1},
                    "return_windows": {"1m": {"total_return": 16.5}, "3m": {"total_return": 21.0}},
                    "signal_context": {"signal_status": "candidate"},
                    "missing_fields": ["rating"],
                    "not_production_model": True,
                }
            ],
            "not_production_model": True,
        },
    )
    review_state = tmp_path / "manual_review_state.json"
    _write_json(review_state, {"items": []})

    generate_evidence_dashboard(
        runs_dir=runs_dir,
        review_state_path=review_state,
        output_dir=tmp_path / "dashboard",
        days=30,
    )

    funds_html = (tmp_path / "dashboard" / "funds.html").read_text(encoding="utf-8")
    detail_html = (tmp_path / "dashboard" / "funds" / "021511.html").read_text(encoding="utf-8")
    assert "Watchlist Fund Details" in funds_html
    assert "021511" in funds_html
    assert "半导体" in funds_html
    assert "Coverage" in funds_html
    assert "Peer Sample" in funds_html
    assert "fund_detail_021511.json" in funds_html
    assert "宏利半导体产业混合发起C" in detail_html
    assert "Data Coverage" in detail_html
    assert "Peer Comparison" in detail_html
    assert "买入" not in funds_html
    assert "卖出" not in funds_html
