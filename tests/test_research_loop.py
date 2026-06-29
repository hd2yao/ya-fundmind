import json
from pathlib import Path

from fund_agent.research_loop import (
    ResearchStepResult,
    aggregate_manual_review_queues,
    render_daily_research_markdown,
    write_daily_research_summary,
    write_run_bundle,
)


def _write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_write_run_bundle_collects_expected_artifacts_and_marks_missing(tmp_path):
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    (output_dir / "fund_agent_report.md").write_text("# report\n", encoding="utf-8")
    (output_dir / "fund_agent_report.html").write_text("<h1>report</h1>\n", encoding="utf-8")
    _write_json(output_dir / "fund_agent_report.json", {"as_of": "2026-06-23"})
    _write_json(output_dir / "snapshots" / "2026-06-23.json", {"as_of": "2026-06-23"})
    _write_json(output_dir / "traces" / "provider-2026-06-23.json", {"as_of": "2026-06-23"})
    _write_json(output_dir / "signal_candidates.json", {"summary": {"eligible_count": 1}})

    bundle = write_run_bundle(output_dir=output_dir, as_of="2026-06-23")

    assert bundle.run_dir == output_dir / "runs" / "2026-06-23"
    assert (bundle.run_dir / "fund_agent_report.json").exists()
    assert (bundle.run_dir / "snapshot.json").exists()
    assert (bundle.run_dir / "provider_trace.json").exists()
    assert "experiment_scoring_report.json" in bundle.missing_artifacts


def test_write_daily_research_summary_records_steps_and_no_main_model_change(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(
        output_dir / "fund_agent_report.json",
        {
            "as_of": "2026-06-23",
            "data_quality_grade": "normal",
            "provider_health": [{"provider": "fixture", "fallback_used": False}],
            "provider_warnings": [],
        },
    )
    _write_json(
        output_dir / "signal_candidates.json",
        {"summary": {"eligible_count": 1, "excluded_count": 2, "display_only_count": 3}},
    )
    _write_json(
        output_dir / "experiment_scoring_report.json",
        {
            "applied_signal_summary": {"total": 0},
            "excluded_signal_summary": {"total": 2},
            "exclusion_diagnostics": {"excluded_by_reason": {"missing_required_signal_data": 2}},
        },
    )
    _write_json(output_dir / "experiment_baseline_comparison.json", {"adjusted_count": 0})
    _write_json(output_dir / "experiment_config_sensitivity.json", {"sensitivity_summary": {"over_sensitive": False}})
    _write_json(
        output_dir / "signal_readiness_review.json",
        {"summary": {"needs_more_data_count": 1}, "recommended_for_experiment": []},
    )
    _write_json(
        output_dir / "manual_review_queue.json",
        [{"signal_id": "tiantian:*", "recommended_status": "needs_data"}],
    )
    (output_dir / "signal_promotion_proposal.md").write_text("- 是否建议进入主模型：no\n", encoding="utf-8")
    steps = (
        ResearchStepResult.success("daily", output_paths=(output_dir / "fund_agent_report.json",)),
    )

    json_path, markdown_path = write_daily_research_summary(
        output_dir=output_dir,
        as_of="2026-06-23",
        steps=steps,
        started_at="2026-06-23T00:00:00+00:00",
        finished_at="2026-06-23T00:00:01+00:00",
        duration_ms=1000,
        status="success",
        missing_artifacts=[],
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert payload["recommend_main_model"] == "no"
    assert payload["main_score_changed"] is False
    assert payload["manual_review_queue"]["total_review_items"] == 1
    assert "没有修改主评分/主风险" in markdown


def test_aggregate_manual_review_queues_counts_repeated_items(tmp_path):
    run_a = tmp_path / "runs" / "2026-06-22"
    run_b = tmp_path / "runs" / "2026-06-23"
    _write_json(
        run_a / "manual_review_queue.json",
        [{"signal_id": "tiantian:return", "recommended_status": "needs_data"}],
    )
    _write_json(
        run_b / "manual_review_queue.json",
        [
            {"signal_id": "tiantian:return", "recommended_status": "needs_data"},
            {"signal_id": "akshare:display", "recommended_status": "rejected"},
        ],
    )

    summary = aggregate_manual_review_queues([run_a, run_b])

    assert summary["total_review_items"] == 3
    assert summary["by_status"]["needs_data"] == 2
    assert summary["by_signal_id"]["tiantian:return"] == 2
    assert summary["repeated_review_items"] == ["tiantian:return"]


def test_render_daily_research_markdown_contains_no_trade_recommendation():
    markdown = render_daily_research_markdown(
        {
            "as_of": "2026-06-23",
            "status": "success",
            "data_quality_grade": "normal",
            "recommend_main_model": "no",
            "steps": [],
            "signal_candidates": {"eligible_count": 0, "excluded_count": 1, "display_only_count": 1},
            "experiment_scoring": {"applied_signal_count": 0},
            "readiness_review": {"needs_more_data_count": 1},
            "manual_review_queue": {"total_review_items": 1},
        }
    )

    assert "买入" not in markdown
    assert "卖出" not in markdown
    assert "没有修改主评分/主风险" in markdown
