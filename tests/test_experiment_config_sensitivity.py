import json
from pathlib import Path

from fund_agent.experiment_scoring import (
    ExperimentScoringConfig,
    run_experiment_config_sensitivity,
)


FIXTURE_DIR = Path("tests/fixtures")


def _payload(name):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_config_sensitivity_outputs_adjustment_counts_for_variants():
    result = run_experiment_config_sensitivity(
        report_payload=_payload("fund_agent_report_experiment_mix.json"),
        signals_payload=_payload("signal_candidates_experiment_mix.json"),
        base_config=ExperimentScoringConfig(max_score_adjustment=1.0),
    )

    names = {item["variant"] for item in result["variants"]}

    assert "max_score_adjustment=0.25" in names
    assert "enable_return_signal=false" in names
    assert "exclude_warning_windows=false" in names
    assert all("adjusted_count" in item for item in result["variants"])
    assert result["warnings"] == []
