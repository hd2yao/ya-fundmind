import json

from fund_agent.ops import build_ops_status, write_latest_summary


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_build_ops_status_reports_latest_run_and_required_artifacts(tmp_path):
    output_dir = tmp_path / "outputs"
    run_dir = output_dir / "runs" / "2026-06-23"
    _write_json(run_dir / "run_metadata.json", {"as_of": "2026-06-23", "status": "success"})
    _write_json(output_dir / "daily_research_summary.json", {"as_of": "2026-06-23", "status": "success"})
    _write_json(output_dir / "weekly_research_summary.json", {"runs_processed": 1})
    _write_json(output_dir / "dashboard" / "manifest.json", {"runs_processed": 1, "pages": ["index.html"]})
    _write_json(output_dir / "long_horizon_stability.json", {"enough_history": False, "blockers": ["insufficient_history"]})
    _write_json(
        output_dir / "market" / "market_intelligence_report.json",
        {
            "as_of": "2026-06-23",
            "total_funds": 6,
            "total_etfs": 2,
            "themes": [{"theme": "沪深300"}],
            "data_quality_summary": {"grade": "warning"},
        },
    )
    _write_json(
        output_dir / "market" / "market_trend_report.json",
        {
            "latest_as_of": "2026-06-23",
            "snapshots_processed": 2,
            "enough_market_history": False,
            "persistent_hot_themes": [{"theme": "半导体"}],
            "new_hot_themes": [{"theme": "芯片"}],
            "data_quality_trend": [{"as_of": "2026-06-23", "data_quality_grade": "warning"}],
        },
    )
    _write_json(
        output_dir / "fund_details" / "watchlist_fund_details.json",
        {
            "as_of": "2026-06-23",
            "detail_count": 2,
            "missing_count": 1,
            "warning_count": 3,
            "coverage_summary": {
                "total_count": 2,
                "average_coverage_ratio": 0.55,
                "missing_coverage_count": 1,
                "unknown_theme_count": 1,
                "peer_insufficient_count": 1,
            },
            "fund_details": [{"code": "021511"}, {"code": "021580"}],
        },
    )
    _write_json(
        output_dir / "portfolio" / "portfolio_report.json",
        {
            "as_of": "2026-06-23",
            "status": "ok",
            "holding_count": 3,
            "total_value": 901.0,
            "cash_available": 500.0,
            "observation_issue_count": 2,
        },
    )

    status = build_ops_status(output_dir)

    assert status["overall_status"] == "ok"
    assert status["ops_ready"] is True
    assert status["research_loop_ready"] is True
    assert status["dashboard_ready"] is False
    assert status["latest_run_available"] is True
    assert status["latest_run_status"] == "success"
    assert status["main_model_ready"] is False
    assert status["main_model_blockers"] == ["insufficient_history"]
    assert "只影响主评分/主风险接入判断" in status["main_model_blocker_explanation"]
    assert "continue_daily_runs" in status["suggested_next_action"]
    assert "continue_feature_development" in status["suggested_next_action"]
    assert "do_not_promote_to_main_model_yet" in status["suggested_next_action"]
    assert status["latest_run"]["as_of"] == "2026-06-23"
    assert status["market_intelligence_available"] is True
    assert status["latest_market_as_of"] == "2026-06-23"
    assert status["latest_market_total_funds"] == 6
    assert status["latest_market_total_etfs"] == 2
    assert status["latest_market_theme_count"] == 1
    assert status["latest_market_data_quality_grade"] == "warning"
    assert status["market_trend_available"] is True
    assert status["latest_market_snapshots_processed"] == 2
    assert status["enough_market_history"] is False
    assert status["latest_market_persistent_hot_count"] == 1
    assert status["latest_market_new_hot_count"] == 1
    assert status["latest_market_data_quality_trend"]
    assert status["fund_detail_available"] is True
    assert status["watchlist_detail_count"] == 2
    assert status["watchlist_detail_missing_count"] == 1
    assert status["watchlist_detail_warning_count"] == 3
    assert status["watchlist_detail_average_coverage_ratio"] == 0.55
    assert status["watchlist_detail_unknown_theme_count"] == 1
    assert status["watchlist_detail_peer_insufficient_count"] == 1
    assert status["latest_fund_detail_as_of"] == "2026-06-23"
    assert status["portfolio_analysis_available"] is True
    assert status["latest_portfolio_status"] == "ok"
    assert status["latest_portfolio_holding_count"] == 3
    assert status["latest_portfolio_observation_issue_count"] == 2
    assert status["latest_portfolio_total_value"] == 901.0
    assert status["artifacts"]["dashboard_index"]["exists"] is False
    assert status["artifacts"]["dashboard_manifest"]["exists"] is True


def test_write_latest_summary_combines_daily_weekly_and_stability(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(
        output_dir / "daily_research_summary.json",
        {
            "as_of": "2026-06-23",
            "status": "success",
            "data_quality_grade": "normal",
            "recommend_main_model": "no",
            "manual_review_queue": {"total_review_items": 4},
        },
    )
    _write_json(
        output_dir / "weekly_research_summary.json",
        {
            "runs_processed": 1,
            "manual_review_state_summary": {"needs_more_data_count": 1},
        },
    )
    _write_json(output_dir / "long_horizon_stability.json", {"enough_history": False, "blockers": ["insufficient_history"]})
    _write_json(
        output_dir / "market" / "market_intelligence_report.json",
        {
            "as_of": "2026-06-23",
            "total_funds": 6,
            "total_etfs": 2,
            "themes": [{"theme": "沪深300"}],
            "data_quality_summary": {"grade": "warning"},
        },
    )
    _write_json(
        output_dir / "market" / "market_trend_report.json",
        {
            "latest_as_of": "2026-06-23",
            "snapshots_processed": 1,
            "enough_market_history": False,
            "persistent_hot_themes": [],
            "new_hot_themes": [],
            "data_quality_trend": [{"as_of": "2026-06-23", "data_quality_grade": "warning"}],
        },
    )
    _write_json(
        output_dir / "fund_details" / "watchlist_fund_details.json",
        {
            "as_of": "2026-06-23",
            "detail_count": 1,
            "missing_count": 0,
            "warning_count": 1,
            "coverage_summary": {
                "total_count": 1,
                "average_coverage_ratio": 0.8,
                "missing_coverage_count": 0,
                "unknown_theme_count": 0,
                "peer_insufficient_count": 0,
            },
            "fund_details": [{"code": "021511"}],
        },
    )
    _write_json(
        output_dir / "portfolio" / "portfolio_report.json",
        {
            "as_of": "2026-06-23",
            "status": "ok",
            "holding_count": 1,
            "total_value": 1000.0,
            "cash_available": 200.0,
            "observation_issue_count": 1,
        },
    )

    path = write_latest_summary(output_dir)
    markdown = path.read_text(encoding="utf-8")

    assert path == output_dir / "latest_summary.md"
    assert "2026-06-23" in markdown
    assert "recommend_main_model: no" in markdown
    assert "ops_ready:" in markdown
    assert "dashboard_ready:" in markdown
    assert "research_loop_ready:" in markdown
    assert "main_model_ready: False" in markdown
    assert "main_model_blockers: insufficient_history" in markdown
    assert "历史 run 不足只影响主评分/主风险接入判断" in markdown
    assert "Market Intelligence" in markdown
    assert "market_total_funds: 6" in markdown
    assert "market_theme_count: 1" in markdown
    assert "Market Trend" in markdown
    assert "market_trend_snapshots_processed: 1" in markdown
    assert "Watchlist Fund Details" in markdown
    assert "fund_detail_available: True" in markdown
    assert "detail_count: 1" in markdown
    assert "average_coverage_ratio: 0.8" in markdown
    assert "unknown_theme_count: 0" in markdown
    assert "peer_insufficient_count: 0" in markdown
    assert "Portfolio Analysis" in markdown
    assert "portfolio_status: ok" in markdown
    assert "portfolio_holding_count: 1" in markdown
    assert "portfolio_observation_issue_count: 1" in markdown
    assert "趋势样本不足只影响板块趋势判断" in markdown
    assert "insufficient_history" in markdown
    assert "不修改主评分/主风险" in markdown
