from pathlib import Path

from fund_agent.signal_review import load_signal_threshold_candidates


def test_load_signal_threshold_candidates_parses_review_status(tmp_path):
    path = tmp_path / "thresholds.yaml"
    path.write_text(
        """
candidates:
  - signal_id_pattern: "tiantian:*:return:*:total_return"
    category: return
    source: tiantian
    direction_hypothesis: positive
    min_required_points: 20
    required_quality_grade: normal
    exclude_if_stale: true
    exclude_if_warning: true
    exclude_if_degraded: true
    max_score_adjustment_candidate: 0.5
    risk_gate_candidate: false
    review_status: proposed
""",
        encoding="utf-8",
    )

    candidates = load_signal_threshold_candidates(path)

    assert len(candidates) == 1
    assert candidates[0]["signal_id_pattern"] == "tiantian:*:return:*:total_return"
    assert candidates[0]["review_status"] == "proposed"
    assert candidates[0]["exclude_if_stale"] is True
