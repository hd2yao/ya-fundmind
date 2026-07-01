import json

from fund_agent.long_horizon import evaluate_long_horizon_stability


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_long_horizon_stability_requires_twenty_runs(tmp_path):
    runs_dir = tmp_path / "runs"
    _write_json(
        runs_dir / "2026-06-23" / "signal_candidates.json",
        {
            "eligible_signals": [],
            "excluded_signals": [],
            "display_only_signals": [{"signal_id": "akshare:display", "category": "display_only"}],
        },
    )
    _write_json(
        runs_dir / "2026-06-23" / "daily_research_summary.json",
        {"as_of": "2026-06-23", "data_quality_grade": "normal", "config_sensitivity": {"over_sensitive": False}},
    )

    result = evaluate_long_horizon_stability(runs_dir=runs_dir, days=30)

    assert result["runs_processed"] == 1
    assert result["minimum_required_runs"] == 20
    assert result["enough_history"] is False
    assert result["main_model_ready"] is False
    assert result["main_model_blockers"] == ["insufficient_history"]
    assert result["readiness_scope"] == "main_model_promotion_only"
    assert "daily_research" in result["non_blocking_for"]
    assert "dashboard" in result["non_blocking_for"]
    assert "feature_development" in result["non_blocking_for"]
    assert result["suggested_review_status"]["akshare:display"] == "rejected"
    assert "insufficient_history" in result["blockers"]


def test_long_horizon_stability_blocks_recurring_missing_or_stale(tmp_path):
    runs_dir = tmp_path / "runs"
    for day in range(1, 22):
        as_of = f"2026-06-{day:02d}"
        _write_json(
            runs_dir / as_of / "signal_candidates.json",
            {
                "eligible_signals": [],
                "excluded_signals": [
                    {
                        "signal_id": "tiantian:return",
                        "category": "return",
                        "excluded_reason": "stale_cache_blocked",
                    }
                ],
                "display_only_signals": [],
            },
        )
        _write_json(
            runs_dir / as_of / "daily_research_summary.json",
            {"as_of": as_of, "data_quality_grade": "normal", "config_sensitivity": {"over_sensitive": False}},
        )

    result = evaluate_long_horizon_stability(runs_dir=runs_dir, days=30)

    assert result["enough_history"] is True
    assert result["main_model_ready"] is False
    assert "recurring_data_quality_blocker" in result["main_model_blockers"]
    assert result["suggested_review_status"]["tiantian:return"] == "blocked"
    assert "recurring_data_quality_blocker" in result["blockers"]
