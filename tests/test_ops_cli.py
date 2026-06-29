import json

from fund_agent.cli import main


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_ops_status_cli_writes_json_and_latest_summary(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(output_dir / "daily_research_summary.json", {"as_of": "2026-06-23", "status": "success"})
    _write_json(output_dir / "weekly_research_summary.json", {"runs_processed": 1})
    _write_json(output_dir / "long_horizon_stability.json", {"enough_history": False, "blockers": []})

    exit_code = main(
        [
            "ops-status",
            "--output-dir",
            str(output_dir),
            "--json-output",
            str(output_dir / "ops_status.json"),
            "--write-latest-summary",
        ]
    )

    status = json.loads((output_dir / "ops_status.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert status["overall_status"] in {"ok", "warning"}
    assert (output_dir / "latest_summary.md").exists()


def test_ops_status_cli_returns_warning_when_outputs_missing(tmp_path):
    output_dir = tmp_path / "outputs"
    exit_code = main(["ops-status", "--output-dir", str(output_dir)])

    assert exit_code == 1
