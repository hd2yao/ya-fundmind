import json

from fund_agent.research_loop import aggregate_manual_review_queues


def test_manual_review_queue_aggregation_handles_missing_files(tmp_path):
    existing = tmp_path / "runs" / "2026-06-23"
    missing = tmp_path / "runs" / "2026-06-24"
    existing.mkdir(parents=True)
    (existing / "manual_review_queue.json").write_text(
        json.dumps(
            [
                {"signal_id": "a", "recommended_status": "needs_data"},
                {"signal_id": "a", "recommended_status": "needs_data"},
                {"signal_id": "b", "recommended_status": "needs_review"},
            ]
        ),
        encoding="utf-8",
    )

    summary = aggregate_manual_review_queues([existing, missing])

    assert summary["total_review_items"] == 3
    assert summary["by_status"] == {"needs_data": 2, "needs_review": 1}
    assert summary["repeated_review_items"] == ["a"]
    assert summary["unresolved_items"] == ["a", "a", "b"]
