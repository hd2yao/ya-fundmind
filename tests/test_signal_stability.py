import json

from fund_agent.signal_candidates import batch_signal_experiment


def _candidate_payload(*, eligible=1, excluded_reason="degraded_window", signal_id="sig-a"):
    return {
        "eligible_signals": [
            {"signal_id": signal_id, "source": "tiantian", "category": "return"}
            for _ in range(eligible)
        ],
        "excluded_signals": [
            {
                "signal_id": "sig-b",
                "source": "tiantian",
                "category": "data_quality",
                "excluded_reason": excluded_reason,
                "quality_grade": "degraded",
            }
        ],
        "display_only_signals": [
            {"signal_id": "sig-c", "source": "tiantian", "category": "display_only"}
        ],
        "summary": {
            "total_signals": eligible + 2,
            "eligible_count": eligible,
            "excluded_count": 1,
            "display_only_count": 1,
            "top_exclusion_reasons": {excluded_reason: 1},
        },
    }


def test_batch_signal_experiment_outputs_stability_statistics(tmp_path):
    input_dir = tmp_path / "history"
    input_dir.mkdir()
    (input_dir / "a.json").write_text(json.dumps(_candidate_payload(eligible=1)), encoding="utf-8")
    (input_dir / "b.json").write_text(
        json.dumps(_candidate_payload(eligible=0, excluded_reason="warning_window")),
        encoding="utf-8",
    )

    result = batch_signal_experiment(input_dir=input_dir)

    assert result["files_processed"] == 2
    assert result["eligible_ratio"] == 0.2
    assert result["excluded_ratio"] == 0.4
    assert result["by_category"]["return"]["eligible_count"] == 1
    assert result["by_source"]["tiantian"]["total_signals"] == 5
    assert result["by_signal_id"]["sig-a"]["signal_presence_count"] == 1
    assert result["by_signal_id"]["sig-a"]["signal_eligible_count"] == 1
    assert result["by_signal_id"]["sig-a"]["signal_eligible_rate"] == 1.0
    assert result["top_exclusion_reasons"]["degraded_window"] == 1
    assert result["top_exclusion_reasons"]["warning_window"] == 1
    assert result["signal_quality_trend"][0]["file"] == "a.json"


def test_batch_signal_experiment_warns_and_skips_missing_fields(tmp_path):
    input_dir = tmp_path / "history"
    input_dir.mkdir()
    (input_dir / "empty.json").write_text(json.dumps({"as_of": "2026-06-23"}), encoding="utf-8")
    (input_dir / "signals.json").write_text(json.dumps(_candidate_payload()), encoding="utf-8")

    result = batch_signal_experiment(input_dir=input_dir)

    assert result["files_processed"] == 2
    assert result["warnings"]
    assert any("empty.json" in warning["file"] for warning in result["warnings"])
