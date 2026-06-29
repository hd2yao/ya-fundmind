import json

from fund_agent.cli import main
from fund_agent.experiment_scoring import render_experiment_baseline_review_markdown


def _comparison_payload():
    return {
        "total_funds": 2,
        "adjusted_count": 1,
        "unchanged_count": 1,
        "avg_score_delta": 0.1,
        "max_score_delta": 0.2,
        "funds_with_adjustments": [{"code": "510300", "score_delta": 0.2}],
        "funds_with_experiment_risk_issues": [{"code": "510300", "issue_count": 1}],
        "main_score_vs_experiment_score": {
            "510300": {"main_score": 8.0, "experiment_score": 8.2, "score_delta": 0.2}
        },
        "applied_signal_summary": {"by_signal_id": {"sig-applied": 1}},
        "excluded_signal_summary": {"by_signal_id": {"sig-excluded": 1}},
        "exclusion_diagnostics": {
            "excluded_by_reason": {"warning_data_blocked": 1}
        },
        "warnings": [],
        "manual_review_required": True,
    }


def test_render_experiment_baseline_review_markdown_explains_not_ready_for_main_model():
    markdown = render_experiment_baseline_review_markdown(_comparison_payload())

    assert "当前实验是否产生分数变化" in markdown
    assert "哪些信号被应用" in markdown
    assert "sig-applied" in markdown
    assert "sig-excluded" in markdown
    assert "不建议进入主模型" in markdown
    assert "warning_data_blocked" in markdown


def test_explain_experiment_baseline_cli_writes_markdown(tmp_path):
    source = tmp_path / "experiment_baseline_comparison.json"
    source.write_text(json.dumps(_comparison_payload()), encoding="utf-8")
    output = tmp_path / "experiment_baseline_review.md"

    exit_code = main(
        [
            "explain-experiment-baseline",
            "--input",
            str(source),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    assert "人工审核项" in output.read_text(encoding="utf-8")
