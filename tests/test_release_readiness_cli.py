import json

from fund_agent.cli import main


def _result(status: str) -> dict:
    return {
        "schema_version": "1.0",
        "generated_at": "2026-07-13T00:00:00+00:00",
        "generator": "fund_agent",
        "release_target": "v2.0.0",
        "status": status,
        "minimum_valid_runs": 3,
        "valid_run_count": 3 if status == "pass" else 0,
        "observed_run_dates": ["2026-07-10", "2026-07-11", "2026-07-12"] if status == "pass" else [],
        "run_observations": [],
        "contract_summary": {"ok": True, "files_checked": 6, "failures": []},
        "performance": {"within_budget": True, "measurements_ms": {}, "budgets_ms": {}},
        "boundaries": {
            "not_production_model": True,
            "main_score_changed": False,
            "main_risk_changed": False,
            "trading_enabled": False,
        },
        "blockers": [],
        "warnings": [],
    }


def test_release_readiness_cli_writes_default_json_and_returns_zero(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(
        "fund_agent.cli.evaluate_release_readiness",
        lambda *args, **kwargs: _result("pass"),
        raising=False,
    )

    exit_code = main(["release-readiness", "--output-dir", str(tmp_path)])

    output = tmp_path / "release" / "v2_release_readiness.json"
    assert exit_code == 0
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "pass"
    assert "valid_runs=3/3" in capsys.readouterr().out


def test_release_readiness_cli_returns_one_for_failed_gate(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "fund_agent.cli.evaluate_release_readiness",
        lambda *args, **kwargs: _result("fail"),
        raising=False,
    )

    exit_code = main(
        [
            "release-readiness",
            "--output-dir",
            str(tmp_path),
            "--json-output",
            str(tmp_path / "custom.json"),
        ]
    )

    assert exit_code == 1
    assert (tmp_path / "custom.json").exists()


def test_validate_contract_cli_accepts_release_readiness(tmp_path) -> None:
    path = tmp_path / "release.json"
    path.write_text(json.dumps(_result("pass")), encoding="utf-8")

    exit_code = main(["validate-contract", "--release-readiness", str(path)])

    assert exit_code == 0
