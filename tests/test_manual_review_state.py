import json

from fund_agent.review_state import (
    list_review_state,
    summarize_review_state,
    update_review_state,
)


def test_update_review_state_creates_and_updates_item(tmp_path):
    state_path = tmp_path / "manual_review_state.json"

    created = update_review_state(
        state_path=state_path,
        review_id="review-1",
        status="needs_more_data",
        note="需要至少 30 天 run history",
        reviewer="alice",
        signal_id="tiantian:return",
        evidence_refs=["outputs/runs/2026-06-23"],
    )
    updated = update_review_state(
        state_path=state_path,
        review_id="review-1",
        status="approved_for_more_experiment",
        note="继续实验",
        reviewer="bob",
    )

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert created["review_id"] == "review-1"
    assert updated["status"] == "approved_for_more_experiment"
    assert payload["items"][0]["reviewer"] == "bob"
    assert payload["items"][0]["decision"] == "approved_for_more_experiment"
    assert payload["items"][0]["evidence_refs"] == ["outputs/runs/2026-06-23"]


def test_summarize_review_state_counts_status_and_notes(tmp_path):
    state_path = tmp_path / "manual_review_state.json"
    update_review_state(
        state_path=state_path,
        review_id="review-1",
        signal_id="a",
        status="needs_more_data",
        note="补样本",
    )
    update_review_state(
        state_path=state_path,
        review_id="review-2",
        signal_id="b",
        status="rejected",
        note="display only",
    )

    summary = summarize_review_state(list_review_state(state_path))

    assert summary["needs_more_data_count"] == 1
    assert summary["rejected_count"] == 1
    assert summary["unresolved_count"] == 1
    assert summary["signals_with_human_notes"] == ["a", "b"]
