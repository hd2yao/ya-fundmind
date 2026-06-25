import json

from fund_agent.cli import main
from fund_agent.signal_candidates import batch_signal_experiment


def _candidate_payload(eligible=1, excluded_reason="degraded_window"):
    return {
        "eligible_signals": [
            {"signal_id": f"eligible-{idx}", "category": "return"}
            for idx in range(eligible)
        ],
        "excluded_signals": [
            {"signal_id": "excluded-1", "category": "data_quality", "excluded_reason": excluded_reason}
        ],
        "display_only_signals": [
            {"signal_id": "display-1", "category": "display_only"}
        ],
        "summary": {
            "total_signals": eligible + 2,
            "eligible_count": eligible,
            "excluded_count": 1,
            "display_only_count": 1,
            "top_exclusion_reasons": {excluded_reason: 1},
        },
    }


def test_batch_signal_experiment_reads_multiple_json_files(tmp_path):
    input_dir = tmp_path / "history"
    input_dir.mkdir()
    (input_dir / "a.json").write_text(json.dumps(_candidate_payload(eligible=2)), encoding="utf-8")
    (input_dir / "b.json").write_text(json.dumps(_candidate_payload(eligible=1, excluded_reason="warning_window")), encoding="utf-8")

    result = batch_signal_experiment(input_dir=input_dir)

    assert result["files_processed"] == 2
    assert result["eligible_count"] == 3
    assert result["excluded_count"] == 2
    assert result["excluded_reason_distribution"]["degraded_window"] == 1
    assert result["excluded_reason_distribution"]["warning_window"] == 1


def test_batch_signal_experiment_cli_writes_report(tmp_path):
    input_dir = tmp_path / "history"
    input_dir.mkdir()
    (input_dir / "a.json").write_text(json.dumps(_candidate_payload()), encoding="utf-8")
    output = tmp_path / "signal_batch_report.json"

    exit_code = main(
        [
            "batch-signal-experiment",
            "--input-dir",
            str(input_dir),
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["files_processed"] == 1
    assert payload["signal_type_counts"]["return"] == 1
