from fund_agent.models import ArtifactDescriptor
from fund_agent.research_evidence import (
    aggregate_quality,
    build_evidence_ref,
    detect_evidence_conflicts,
    evaluate_artifact_quality,
)


def _descriptor(**overrides) -> ArtifactDescriptor:
    values = {
        "artifact_id": "artifact-a",
        "artifact_type": "report",
        "path": "fund_agent_report.json",
        "schema_version": "1.0",
        "as_of": "2026-07-12",
        "generated_at": "2026-07-12T00:00:00+00:00",
        "source": "akshare",
        "quality_grade": "normal",
        "stale": False,
        "content_hash": "a" * 64,
    }
    values.update(overrides)
    return ArtifactDescriptor(**values)


def test_quality_gate_marks_clean_artifact_normal():
    decision = evaluate_artifact_quality(_descriptor(), {"provider_health": []})

    assert decision.grade == "normal"
    assert decision.review_required is False
    assert decision.reasons == ()


def test_quality_gate_marks_fallback_and_regular_warnings_warning():
    decision = evaluate_artifact_quality(
        _descriptor(),
        {
            "provider_health": [{"fallback_used": True}],
            "provider_warnings": [{"code": "skipped_rows", "severity": "warning"}],
        },
    )

    assert decision.grade == "warning"
    assert decision.review_required is False
    assert "provider_fallback" in decision.reasons
    assert "provider_warning:skipped_rows" in decision.reasons


def test_quality_gate_marks_stale_or_degraded_artifacts_degraded():
    stale = evaluate_artifact_quality(_descriptor(stale=True), {})
    degraded = evaluate_artifact_quality(_descriptor(quality_grade="degraded"), {})

    assert stale.grade == "degraded"
    assert stale.review_required is True
    assert stale.reasons == ("stale_artifact",)
    assert degraded.grade == "degraded"
    assert degraded.review_required is True
    assert degraded.reasons == ("artifact_quality:degraded",)


def test_quality_gate_blocks_critical_provider_warning():
    decision = evaluate_artifact_quality(
        _descriptor(),
        {"provider_warnings": [{"code": "all_watchlist_missing", "severity": "critical"}]},
    )

    assert decision.grade == "blocked"
    assert decision.review_required is True
    assert decision.reasons == ("critical_provider_warning:all_watchlist_missing",)


def test_quality_gate_marks_legacy_schema_and_insufficient_sample_warning():
    decision = evaluate_artifact_quality(
        _descriptor(warnings=("schema_version_missing",)),
        {"warnings": ["insufficient_sample_themes:2"]},
    )

    assert decision.grade == "warning"
    assert "legacy_schema" in decision.reasons
    assert "insufficient_sample" in decision.reasons


def test_conflict_gate_only_flags_cross_source_different_values():
    source_a = _descriptor(artifact_id="artifact-a", source="akshare", path="a.json")
    source_b = _descriptor(artifact_id="artifact-b", source="tiantian", path="b.json")
    same_a = build_evidence_ref(source_a, {"rating": "5"}, json_pointer="/rating", claim_type="fund.rating")
    same_b = build_evidence_ref(source_b, {"rating": "5"}, json_pointer="/rating", claim_type="fund.rating")
    different_b = build_evidence_ref(source_b, {"rating": "4"}, json_pointer="/rating", claim_type="fund.rating")

    assert detect_evidence_conflicts((same_a, same_b)) == ()
    conflicts = detect_evidence_conflicts((same_a, different_b))

    assert len(conflicts) == 1
    assert conflicts[0].claim_type == "fund.rating"
    assert conflicts[0].sources == ("akshare", "tiantian")
    assert conflicts[0].quality_grade == "degraded"
    assert conflicts[0].review_required is True


def test_aggregate_quality_uses_worst_grade_and_review_requirement():
    decisions = (
        evaluate_artifact_quality(_descriptor(), {}),
        evaluate_artifact_quality(_descriptor(stale=True), {}),
    )

    aggregate = aggregate_quality(decisions)

    assert aggregate.grade == "degraded"
    assert aggregate.review_required is True
    assert aggregate.reasons == ("stale_artifact",)
