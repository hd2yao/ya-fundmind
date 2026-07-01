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
    for page in ["index.html", "runs.html", "signals.html", "review.html", "data_quality.html"]:
        html = (dashboard / page).read_text(encoding="utf-8")
        assert "not_production_model=true" in html
        assert "买入" not in html
        assert "卖出" not in html
    index_html = (dashboard / "index.html").read_text(encoding="utf-8")
    assert "research_loop_ready" in index_html
    assert "dashboard_ready" in index_html
    assert "insufficient_history 只影响主评分/主风险接入" in index_html
    assert "当前系统可继续运行" in index_html
    assert sorted(manifest["pages"]) == [
        "data_quality.html",
        "index.html",
        "review.html",
        "runs.html",
        "signals.html",
    ]
