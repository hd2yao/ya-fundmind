import json
from pathlib import Path

from fund_agent.experiment_scoring import (
    ExperimentScoringConfig,
    compare_experiment_baseline,
    run_experiment_scoring,
)


FIXTURE_DIR = Path("tests/fixtures")


def _payload(name):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_compare_experiment_baseline_outputs_main_vs_experiment_scores():
    report = _payload("fund_agent_report_experiment_mix.json")
    experiment = run_experiment_scoring(
        report_payload=report,
        signals_payload=_payload("signal_candidates_experiment_mix.json"),
        config=ExperimentScoringConfig(),
    )

    result = compare_experiment_baseline(report_payload=report, experiment_payload=experiment)

    assert result["total_funds"] == 2
    assert result["adjusted_count"] == 1
    assert result["unchanged_count"] == 1
    assert result["funds_with_adjustments"][0]["code"] == "510300"
    assert result["main_score_vs_experiment_score"]["510300"]["main_score"] == 8.0
    assert result["main_score_vs_experiment_score"]["510300"]["experiment_score"] != 8.0
    assert result["manual_review_required"] is True


def test_compare_experiment_baseline_diagnoses_zero_applied_signals():
    report = _payload("fund_agent_report_experiment_mix.json")
    experiment = run_experiment_scoring(
        report_payload=report,
        signals_payload={
            "eligible_signals": [
                {
                    "signal_id": "bad:warning",
                    "source": "tiantian",
                    "code": "510300",
                    "category": "return",
                    "value": 1.0,
                    "quality_grade": "warning",
                    "eligible": True,
                }
            ],
            "excluded_signals": [],
            "display_only_signals": [],
        },
        config=ExperimentScoringConfig(),
    )

    result = compare_experiment_baseline(report_payload=report, experiment_payload=experiment)

    assert result["adjusted_count"] == 0
    assert result["warnings"]
    assert "applied signals = 0" in result["warnings"][0]["message"]
