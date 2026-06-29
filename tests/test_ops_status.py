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

    status = build_ops_status(output_dir)

    assert status["overall_status"] == "ok"
    assert status["latest_run"]["as_of"] == "2026-06-23"
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

    path = write_latest_summary(output_dir)
    markdown = path.read_text(encoding="utf-8")

    assert path == output_dir / "latest_summary.md"
    assert "2026-06-23" in markdown
    assert "recommend_main_model: no" in markdown
    assert "insufficient_history" in markdown
    assert "不修改主评分/主风险" in markdown
