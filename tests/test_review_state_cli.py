import json

from fund_agent.cli import main


def test_update_and_list_review_state_cli(tmp_path, capsys):
    state_path = tmp_path / "manual_review_state.json"
    summary_path = tmp_path / "manual_review_state_summary.json"

    update_exit = main(
        [
            "update-review-state",
            "--review-id",
            "demo-review",
            "--status",
            "needs_more_data",
            "--note",
            "需要更多历史 run",
            "--state",
            str(state_path),
            "--signal-id",
            "tiantian:return",
        ]
    )
    list_exit = main(
        [
            "list-review-state",
            "--state",
            str(state_path),
            "--summary-output",
            str(summary_path),
        ]
    )

    payload = json.loads(state_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    output = capsys.readouterr().out
    assert update_exit == 0
    assert list_exit == 0
    assert payload["items"][0]["status"] == "needs_more_data"
    assert summary["needs_more_data_count"] == 1
    assert "needs_more_data_count=1" in output
