import json

from fund_agent.cli import main


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_weekly_research_cli_aggregates_runs_and_missing_dates(tmp_path):
    runs_dir = tmp_path / "runs"
    _write_json(
        runs_dir / "2026-06-21" / "daily_research_summary.json",
        {
            "as_of": "2026-06-21",
            "data_quality_grade": "normal",
            "signal_candidates": {"eligible_count": 1, "excluded_count": 2},
            "experiment_scoring": {"applied_signal_count": 0},
            "readiness_review": {"needs_more_data_count": 1},
        },
    )
    _write_json(
        runs_dir / "2026-06-23" / "daily_research_summary.json",
        {
            "as_of": "2026-06-23",
            "data_quality_grade": "warning",
            "signal_candidates": {"eligible_count": 0, "excluded_count": 3},
            "experiment_scoring": {"applied_signal_count": 0},
            "readiness_review": {"needs_more_data_count": 2},
        },
    )
    _write_json(
        runs_dir / "2026-06-23" / "manual_review_queue.json",
        [{"signal_id": "tiantian:return", "recommended_status": "needs_data"}],
    )

    exit_code = main(
        [
            "weekly-research",
            "--runs-dir",
            str(runs_dir),
            "--output",
            str(tmp_path / "weekly_research_summary.md"),
            "--json-output",
            str(tmp_path / "weekly_research_summary.json"),
            "--days",
            "3",
        ]
    )

    payload = json.loads((tmp_path / "weekly_research_summary.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "weekly_research_summary.md").read_text(encoding="utf-8")
    assert exit_code == 0
    assert payload["runs_processed"] == 2
    assert payload["missing_runs"] == ["2026-06-22"]
    assert payload["run_continuity"]["missing_runs"] == ["2026-06-22"]
    assert payload["main_model_readiness"]["ready"] is False
    assert "run_continuity_issue" in payload["main_model_readiness"]["blockers"]
    assert "continue_feature_development" in payload["normal_development_next_actions"]
    assert payload["manual_review_queue_summary"]["total_review_items"] == 1
    assert "Run Continuity" in markdown
    assert "Main Model Readiness" in markdown
    assert "不阻塞 Market Intelligence / Fund Detail / Research Console 开发" in markdown
    assert "买入" not in markdown
    assert "卖出" not in markdown


def test_weekly_research_cli_reads_manual_review_state(tmp_path):
    runs_dir = tmp_path / "runs"
    _write_json(
        runs_dir / "2026-06-23" / "daily_research_summary.json",
        {
            "as_of": "2026-06-23",
            "data_quality_grade": "normal",
            "signal_candidates": {"eligible_count": 0, "excluded_count": 1},
            "experiment_scoring": {"applied_signal_count": 0},
            "readiness_review": {"needs_more_data_count": 1},
        },
    )
    state_path = tmp_path / "manual_review_state.json"
    _write_json(
        state_path,
        {
            "items": [
                {
                    "review_id": "r1",
                    "signal_id": "tiantian:return",
                    "status": "needs_more_data",
                    "note": "补历史",
                }
            ]
        },
    )

    exit_code = main(
        [
            "weekly-research",
            "--runs-dir",
            str(runs_dir),
            "--review-state",
            str(state_path),
            "--output",
            str(tmp_path / "weekly_research_summary.md"),
            "--json-output",
            str(tmp_path / "weekly_research_summary.json"),
            "--days",
            "7",
        ]
    )

    payload = json.loads((tmp_path / "weekly_research_summary.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "weekly_research_summary.md").read_text(encoding="utf-8")
    assert exit_code == 0
    assert payload["manual_review_state_summary"]["needs_more_data_count"] == 1
    assert payload["manual_review_state_summary"]["signals_with_human_notes"] == ["tiantian:return"]
    assert "manual_review_state" in markdown
