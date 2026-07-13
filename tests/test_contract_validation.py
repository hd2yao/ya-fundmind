import json

from fund_agent.agents import run_research
from fund_agent.cli import main
from fund_agent.contract import validate_contract_file, validate_output_dir
from fund_agent.models import FundRecord, ProviderHealth
from fund_agent.report import write_json_report
from fund_agent.snapshot import write_snapshot
from fund_agent.trace import write_provider_trace


def _result():
    health = ProviderHealth(
        provider="fixture",
        started_at="2026-06-23T00:00:00+00:00",
        finished_at="2026-06-23T00:00:01+00:00",
        duration_ms=1000,
        live_row_count=1,
        mapped_row_count=1,
    )
    return run_research(
        [FundRecord(code="510300", name="沪深300ETF", category="ETF", nav=5.0)],
        as_of="2026-06-23",
        provider_health=(health,),
    )


def test_current_json_report_passes_contract_validation(tmp_path):
    path = write_json_report(_result(), tmp_path)

    result = validate_contract_file(path, "report")

    assert result.ok is True
    assert result.warnings == ()


def test_current_provider_trace_passes_contract_validation(tmp_path):
    path = write_provider_trace(_result(), tmp_path)

    result = validate_contract_file(path, "trace")

    assert result.ok is True
    assert result.errors == ()


def test_current_snapshot_passes_contract_validation(tmp_path):
    path = write_snapshot(_result(), tmp_path)

    result = validate_contract_file(path, "snapshot")

    assert result.ok is True
    assert result.errors == ()


def test_legacy_snapshot_without_schema_version_is_warning_only(tmp_path):
    path = tmp_path / "legacy-snapshot.json"
    path.write_text(
        json.dumps(
            {
                "as_of": "2026-06-22",
                "candidates": {},
                "valuations": {},
                "portfolio": None,
            }
        ),
        encoding="utf-8",
    )

    result = validate_contract_file(path, "snapshot")

    assert result.ok is True
    assert any("schema_version" in warning for warning in result.warnings)


def test_missing_core_field_fails_contract_validation(tmp_path):
    path = tmp_path / "bad-report.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "generated_at": "2026-06-23T00:00:00+00:00",
                "generator": "fund_agent",
                "as_of": "2026-06-23",
            }
        ),
        encoding="utf-8",
    )

    result = validate_contract_file(path, "report")

    assert result.ok is False
    assert any("data_quality_grade" in error for error in result.errors)


def test_json_report_with_optional_tiantian_fields_still_validates(tmp_path):
    path = write_json_report(_result(), tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["fund_details"] = [
        {
            "code": "510300",
            "name": "沪深300ETF",
            "source": "tiantian",
        }
    ]
    payload["nav_history_summary"] = {
        "510300": {
            "count": 2,
            "source": "tiantian",
            "windows": {
                "1m": {
                    "count": 2,
                    "source": "tiantian",
                    "data_quality_grade": "warning",
                }
            },
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_contract_file(path, "report")

    assert result.ok is True


def test_provider_trace_with_tiantian_cache_window_extensions_still_validates(tmp_path):
    health = ProviderHealth(
        provider="tiantian",
        started_at="2026-06-23T00:00:00+00:00",
        finished_at="2026-06-23T00:00:01+00:00",
        duration_ms=1000,
        cache_read_count=3,
        fallback_used=True,
        fallback_source="cache:tiantian",
        metadata={
            "windows_requested": ["1m", "3m"],
            "windows_generated": ["1m", "3m"],
        },
    )
    result = run_research(
        [FundRecord(code="510300", name="沪深300ETF", category="ETF", nav=5.0)],
        as_of="2026-06-23",
        provider_health=(health,),
    )
    path = write_provider_trace(result, tmp_path)

    validation = validate_contract_file(path, "trace")

    assert validation.ok is True


def test_snapshot_with_optional_signal_quality_summary_still_validates(tmp_path):
    path = write_snapshot(_result(), tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["signal_quality_summary"] = {
        "total_signals": 3,
        "eligible_count": 1,
        "excluded_count": 1,
        "degraded_count": 1,
        "warning_count": 0,
        "display_only_count": 1,
        "top_exclusion_reasons": {"degraded_window": 1},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_contract_file(path, "snapshot")

    assert result.ok is True


def test_snapshot_with_optional_experiment_score_summary_still_validates(tmp_path):
    path = write_snapshot(_result(), tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["experiment_score_summary"] = {
        "total_funds": 1,
        "adjusted_count": 1,
        "unchanged_count": 0,
        "avg_score_delta": 0.2,
        "max_score_delta": 0.2,
        "applied_signal_count": 1,
        "excluded_signal_count": 0,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_contract_file(path, "snapshot")

    assert result.ok is True


def test_validate_output_dir_checks_all_known_outputs(tmp_path):
    result = _result()
    write_json_report(result, tmp_path)
    write_provider_trace(result, tmp_path)
    write_snapshot(result, tmp_path)

    summary = validate_output_dir(tmp_path)

    assert summary.ok is True
    assert len(summary.results) == 3


def test_validate_contract_cli_returns_zero_for_valid_outputs(tmp_path):
    main(["demo", "--output-dir", str(tmp_path), "--as-of", "2026-06-23"])

    exit_code = main(["validate-contract", "--output-dir", str(tmp_path)])

    assert exit_code == 0


def test_validate_contract_cli_returns_one_for_invalid_report(tmp_path):
    path = tmp_path / "fund_agent_report.json"
    path.write_text("{}", encoding="utf-8")

    exit_code = main(["validate-contract", "--report", str(path)])

    assert exit_code == 1


def test_research_context_contract_accepts_core_fields_and_unknown_optional_fields(tmp_path):
    path = tmp_path / "research_context.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "generated_at": "2026-07-12T00:00:00+00:00",
                "generator": "fund_agent",
                "topic": "market",
                "status": "ok",
                "as_of": "2026-07-12",
                "code": None,
                "artifacts": [],
                "data": {},
                "warnings": [],
                "metadata": {"compact": True},
                "future_optional": True,
            }
        ),
        encoding="utf-8",
    )

    result = validate_contract_file(path, "research_context")

    assert result.ok is True


def test_research_context_contract_rejects_missing_core_field_and_wrong_shape(tmp_path):
    path = tmp_path / "research_context.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "generated_at": "2026-07-12T00:00:00+00:00",
                "generator": "fund_agent",
                "topic": "market",
                "status": "ok",
                "as_of": "2026-07-12",
                "code": None,
                "artifacts": {},
                "warnings": [],
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )

    result = validate_contract_file(path, "research_context")

    assert result.ok is False
    assert "Missing core field: data" in result.errors
    assert "Field must be a list: artifacts" in result.errors


def test_research_context_contract_rejects_unknown_topic_and_status(tmp_path):
    path = tmp_path / "research_context.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "generated_at": "2026-07-12T00:00:00+00:00",
                "generator": "fund_agent",
                "topic": "markdown",
                "status": "complete",
                "as_of": None,
                "code": None,
                "artifacts": [],
                "data": {},
                "warnings": [],
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )

    result = validate_contract_file(path, "research_context")

    assert result.ok is False
    assert "Unsupported research topic: markdown" in result.errors
    assert "Unsupported research context status: complete" in result.errors


def test_evidence_bundle_contract_accepts_cited_findings(tmp_path):
    path = tmp_path / "research_evidence.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "generated_at": "2026-07-12T00:00:00+00:00",
                "generator": "fund_agent",
                "topic": "market",
                "status": "ok",
                "as_of": "2026-07-12",
                "code": None,
                "quality_grade": "normal",
                "review_required": False,
                "findings": [
                    {
                        "finding_id": "finding-1",
                        "topic": "market",
                        "category": "breadth",
                        "label": "基金总数",
                        "value": 10,
                        "code": None,
                        "quality_grade": "normal",
                        "evidence_ids": ["evidence-1"],
                        "review_required": False,
                        "warnings": [],
                        "metadata": {"claim_type": "market.total_funds"},
                    }
                ],
                "evidence": [
                    {
                        "evidence_id": "evidence-1",
                        "artifact_id": "artifact-1",
                        "artifact_type": "market_intelligence",
                        "path": "market/report.json",
                        "content_hash": "a" * 64,
                        "json_pointer": "",
                        "claim_type": "market.total_funds",
                        "as_of": "2026-07-12",
                        "source": "fixture",
                        "quality_grade": "normal",
                        "stale": False,
                        "value": {"total_funds": 10},
                        "excerpt": "{\"total_funds\":10}",
                        "metadata": {},
                    }
                ],
                "data_gaps": [],
                "warnings": [],
                "metadata": {},
                "future_optional": True,
            }
        ),
        encoding="utf-8",
    )

    result = validate_contract_file(path, "evidence_bundle")

    assert result.ok is True


def test_evidence_bundle_contract_rejects_uncited_or_missing_evidence(tmp_path):
    path = tmp_path / "research_evidence.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "generated_at": "2026-07-12T00:00:00+00:00",
                "generator": "fund_agent",
                "topic": "market",
                "status": "ok",
                "as_of": "2026-07-12",
                "code": None,
                "quality_grade": "normal",
                "review_required": False,
                "findings": [
                    {"finding_id": "finding-1", "evidence_ids": []},
                    {"finding_id": "finding-2", "evidence_ids": ["evidence-missing"]},
                ],
                "evidence": [
                    {
                        "evidence_id": "evidence-other",
                        "artifact_id": "artifact-1",
                        "path": "market/report.json",
                        "json_pointer": "/total_funds",
                        "claim_type": "market.total_funds",
                    }
                ],
                "data_gaps": [],
                "warnings": [],
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )

    result = validate_contract_file(path, "evidence_bundle")

    assert result.ok is False
    assert "Finding must reference at least one evidence id: finding-1" in result.errors
    assert "Finding references unknown evidence id: evidence-missing" in result.errors
    assert "Evidence item missing field: content_hash" in result.errors
