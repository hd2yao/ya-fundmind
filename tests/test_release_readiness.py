import json
from pathlib import Path

import pytest

from fund_agent.release_readiness import evaluate_release_readiness, inspect_run_bundle


GENERATED_AT = "2026-07-13T00:00:00+00:00"


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _report(as_of: str, provider_health: list[dict]) -> dict:
    return {
        "schema_version": "1.0",
        "generated_at": GENERATED_AT,
        "generator": "fund_agent",
        "as_of": as_of,
        "data_quality_grade": "normal",
        "provider_health": provider_health,
        "provider_warnings": [],
        "candidates": [],
        "valuations": {},
        "portfolio": None,
        "risk_issues": [],
        "snapshot_delta": {},
        "report_metadata": {
            "not_production_model": True,
            "main_score_changed": False,
            "main_risk_changed": False,
        },
    }


def _snapshot(as_of: str, provider_health: list[dict]) -> dict:
    return {
        "schema_version": "1.0",
        "generated_at": GENERATED_AT,
        "generator": "fund_agent",
        "as_of": as_of,
        "candidates": {},
        "valuations": {},
        "portfolio": None,
        "provider_health": provider_health,
        "data_quality_grade": "normal",
    }


def _trace(as_of: str, provider_health: list[dict]) -> dict:
    return {
        "schema_version": "1.0",
        "generated_at": GENERATED_AT,
        "generator": "fund_agent",
        "as_of": as_of,
        "providers": provider_health,
    }


def _write_contract_baseline(output_dir: Path, as_of: str = "2026-07-12") -> None:
    provider_health = [_provider()]
    _write_json(output_dir / "fund_agent_report.json", _report(as_of, provider_health))
    _write_json(output_dir / "snapshots" / f"{as_of}.json", _snapshot(as_of, provider_health))
    _write_json(output_dir / "traces" / f"provider-{as_of}.json", _trace(as_of, provider_health))
    _write_json(
        output_dir / "market" / "market_intelligence_report.json",
        {
            "schema_version": "1.0",
            "generated_at": GENERATED_AT,
            "generator": "fund_agent",
            "as_of": as_of,
            "source": "akshare",
            "total_funds": 10,
            "total_etfs": 2,
            "themes": [],
            "top_themes": [],
            "hot_theme_candidates": [],
            "insufficient_sample_themes": [],
            "data_quality_summary": {"grade": "normal"},
            "warnings": [],
        },
    )


def _provider(
    *,
    provider: str = "akshare",
    live_rows: int = 100,
    fallback: bool = False,
    warnings: list[dict] | None = None,
) -> dict:
    return {
        "provider": provider,
        "provider_version": "1.0",
        "live_row_count": live_rows,
        "mapped_row_count": live_rows,
        "skipped_row_count": 0,
        "cache_write_count": live_rows,
        "fallback_used": fallback,
        "fallback_reason": "network_error" if fallback else None,
        "fallback_source": "cache:akshare" if fallback else None,
        "warnings": list(warnings or []),
    }


def _write_run(
    output_dir: Path,
    as_of: str,
    *,
    provider: str = "akshare",
    live_rows: int = 100,
    fallback: bool = False,
    quality: str = "normal",
    warnings: list[dict] | None = None,
    missing_artifacts: list[str] | None = None,
    main_score_changed: bool = False,
    main_risk_changed: bool = False,
    provenance: dict | None = None,
) -> Path:
    run_dir = output_dir / "runs" / as_of
    provider_health = [
        _provider(
            provider=provider,
            live_rows=live_rows,
            fallback=fallback,
            warnings=warnings,
        )
    ]
    summary = {
        "as_of": as_of,
        "status": "success",
        "data_quality_grade": quality,
        "not_production_model": True,
        "main_score_changed": main_score_changed,
        "main_risk_changed": main_risk_changed,
        "missing_artifacts": list(missing_artifacts or []),
        "data_source": {
            "provider_health": provider_health,
            "provider_warning_count": len(warnings or []),
        },
    }
    metadata = {
        "as_of": as_of,
        "status": "success",
        "steps": [
            {"step_name": "daily", "status": "success"},
            {"step_name": "validate_contract", "status": "success"},
        ],
        **({"provenance": provenance} if provenance is not None else {}),
    }
    _write_json(run_dir / "daily_research_summary.json", summary)
    _write_json(run_dir / "run_metadata.json", metadata)
    _write_json(run_dir / "fund_agent_report.json", _report(as_of, provider_health))
    _write_json(run_dir / "snapshot.json", _snapshot(as_of, provider_health))
    _write_json(run_dir / "provider_trace.json", _trace(as_of, provider_health))
    return run_dir


def test_release_readiness_passes_with_three_distinct_real_valid_runs(tmp_path) -> None:
    output_dir = tmp_path / "outputs"
    _write_contract_baseline(output_dir)
    for as_of, quality in (
        ("2026-07-10", "normal"),
        ("2026-07-11", "warning"),
        ("2026-07-12", "normal"),
    ):
        _write_run(output_dir, as_of, quality=quality)

    result = evaluate_release_readiness(
        output_dir,
        minimum_valid_runs=3,
        release_target="v2.0.0-rc.1",
    )

    assert result["status"] == "pass"
    assert result["valid_run_count"] == 3
    assert result["observed_run_dates"] == ["2026-07-10", "2026-07-11", "2026-07-12"]
    assert result["blockers"] == []
    assert result["contract_summary"]["ok"] is True
    assert result["performance"]["within_budget"] is True
    assert result["boundaries"] == {
        "not_production_model": True,
        "main_score_changed": False,
        "main_risk_changed": False,
        "trading_enabled": False,
    }


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"provider": "fixture"}, "non_live_provider"),
        ({"provider": "cache:akshare"}, "non_live_provider"),
        ({"fallback": True}, "provider_fallback_used"),
        ({"quality": "degraded"}, "data_quality_degraded"),
        ({"live_rows": 0}, "provider_live_rows_missing"),
        (
            {"warnings": [{"code": "provider_failed", "severity": "critical"}]},
            "critical_provider_warning",
        ),
        ({"main_score_changed": True}, "main_score_changed"),
        ({"main_risk_changed": True}, "main_risk_changed"),
    ],
)
def test_run_observation_excludes_non_release_evidence(tmp_path, overrides, reason) -> None:
    run_dir = _write_run(tmp_path / "outputs", "2026-07-12", **overrides)

    observation = inspect_run_bundle(run_dir)

    assert observation["status"] == "excluded"
    assert reason in observation["reasons"]


def test_run_observation_requires_contracts_steps_and_artifacts(tmp_path) -> None:
    run_dir = _write_run(tmp_path / "outputs", "2026-07-12")
    (run_dir / "provider_trace.json").unlink()
    metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    metadata["steps"][1]["status"] = "failed"
    _write_json(run_dir / "run_metadata.json", metadata)

    observation = inspect_run_bundle(run_dir)

    assert observation["status"] == "excluded"
    assert "required_artifact_missing:provider_trace.json" in observation["reasons"]
    assert "required_step_failed:validate_contract" in observation["reasons"]


def test_run_observation_uses_strict_contract_validation(tmp_path) -> None:
    run_dir = _write_run(tmp_path / "outputs", "2026-07-12")
    report_path = run_dir / "fund_agent_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["schema_version"] = "2.0"
    report["generated_at"] = "not-a-timestamp"
    _write_json(report_path, report)

    observation = inspect_run_bundle(run_dir)

    assert observation["status"] == "excluded"
    assert "artifact_contract_invalid:fund_agent_report.json" in observation["reasons"]


def test_release_readiness_contract_summary_is_strict(tmp_path) -> None:
    output_dir = tmp_path / "outputs"
    _write_contract_baseline(output_dir)
    _write_run(output_dir, "2026-07-12")
    report_path = output_dir / "fund_agent_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["schema_version"] = "2.0"
    _write_json(report_path, report)

    result = evaluate_release_readiness(output_dir, minimum_valid_runs=1)

    assert result["status"] == "fail"
    assert "contract_validation_failed" in result["blockers"]


def test_release_readiness_fails_when_real_history_is_insufficient(tmp_path) -> None:
    output_dir = tmp_path / "outputs"
    _write_contract_baseline(output_dir)
    _write_run(output_dir, "2026-07-12")

    result = evaluate_release_readiness(output_dir, minimum_valid_runs=3)

    assert result["status"] == "fail"
    assert result["valid_run_count"] == 1
    assert "insufficient_valid_release_runs" in result["blockers"]


def test_post_rc_mode_requires_matching_clean_scheduler_provenance(tmp_path) -> None:
    output_dir = tmp_path / "outputs"
    _write_contract_baseline(output_dir)
    commit = "a" * 40
    _write_run(
        output_dir,
        "2026-07-12",
        provenance={
            "app_version": "2.0.0rc1",
            "git_commit": commit,
            "git_dirty": False,
            "trigger": "daily_ops",
            "python_version": "3.12.0",
        },
    )

    result = evaluate_release_readiness(
        output_dir,
        minimum_valid_runs=1,
        observation_mode="post_rc",
        required_app_version="2.0.0rc1",
        required_git_commit=commit,
    )

    assert result["status"] == "pass"
    assert result["observation_mode"] == "post_rc"
    assert result["valid_run_count"] == 1
    assert result["run_observations"][0]["provenance"]["git_commit"] == commit


@pytest.mark.parametrize(
    ("provenance", "reason"),
    (
        (None, "run_provenance_missing"),
        (
            {
                "app_version": "1.5.0",
                "git_commit": "a" * 40,
                "git_dirty": False,
                "trigger": "daily_ops",
            },
            "run_app_version_mismatch",
        ),
        (
            {
                "app_version": "2.0.0rc1",
                "git_commit": "b" * 40,
                "git_dirty": False,
                "trigger": "daily_ops",
            },
            "run_git_commit_mismatch",
        ),
        (
            {
                "app_version": "2.0.0rc1",
                "git_commit": "a" * 40,
                "git_dirty": True,
                "trigger": "daily_ops",
            },
            "run_git_dirty",
        ),
        (
            {
                "app_version": "2.0.0rc1",
                "git_commit": "a" * 40,
                "git_dirty": False,
                "trigger": "manual",
            },
            "run_trigger_not_scheduler",
        ),
    ),
)
def test_post_rc_mode_excludes_unprovenanced_runs(tmp_path, provenance, reason) -> None:
    run_dir = _write_run(
        tmp_path / "outputs",
        "2026-07-12",
        provenance=provenance,
    )

    observation = inspect_run_bundle(
        run_dir,
        observation_mode="post_rc",
        required_app_version="2.0.0rc1",
        required_git_commit="a" * 40,
    )

    assert observation["status"] == "excluded"
    assert reason in observation["reasons"]


def test_post_rc_mode_fails_closed_without_required_version_and_commit(tmp_path) -> None:
    output_dir = tmp_path / "outputs"
    _write_contract_baseline(output_dir)
    _write_run(output_dir, "2026-07-12")

    result = evaluate_release_readiness(
        output_dir,
        minimum_valid_runs=1,
        observation_mode="post_rc",
    )

    assert result["status"] == "fail"
    assert "required_app_version_missing" in result["blockers"]
    assert "required_git_commit_missing" in result["blockers"]


def test_final_release_target_cannot_pass_historical_compat_mode(tmp_path) -> None:
    output_dir = tmp_path / "outputs"
    _write_contract_baseline(output_dir)
    _write_run(output_dir, "2026-07-12")

    result = evaluate_release_readiness(
        output_dir,
        minimum_valid_runs=1,
        release_target="v2.0.0",
        observation_mode="historical_compat",
    )

    assert result["status"] == "fail"
    assert "final_release_requires_post_rc_observation" in result["blockers"]
