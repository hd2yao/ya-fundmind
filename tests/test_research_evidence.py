from fund_agent.models import ArtifactDescriptor
from fund_agent.research_evidence import (
    build_evidence_ref,
    build_finding,
    escape_json_pointer_token,
    resolve_json_pointer,
)


def _descriptor(**overrides) -> ArtifactDescriptor:
    values = {
        "artifact_id": "artifact-123",
        "artifact_type": "market_intelligence",
        "path": "market/market_intelligence_report.json",
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


def test_json_pointer_escape_and_resolve_follow_rfc6901():
    payload = {"a/b": {"~key": [{"value": 42}]}}
    pointer = f"/{escape_json_pointer_token('a/b')}/{escape_json_pointer_token('~key')}/0/value"

    assert pointer == "/a~1b/~0key/0/value"
    assert resolve_json_pointer(payload, pointer) == 42
    assert resolve_json_pointer(payload, "") == payload


def test_json_pointer_rejects_invalid_or_missing_paths():
    payload = {"items": []}

    for pointer in ("items", "/missing", "/items/0", "/items/not-an-index"):
        try:
            resolve_json_pointer(payload, pointer)
        except ValueError as exc:
            assert "JSON Pointer" in str(exc)
        else:  # pragma: no cover - assertion helper
            raise AssertionError(f"expected invalid pointer: {pointer}")


def test_evidence_ref_is_stable_and_preserves_source_metadata():
    descriptor = _descriptor()
    payload = {"total_funds": 21488}

    first = build_evidence_ref(
        descriptor,
        payload,
        json_pointer="/total_funds",
        claim_type="market.total_funds",
    )
    second = build_evidence_ref(
        descriptor,
        payload,
        json_pointer="/total_funds",
        claim_type="market.total_funds",
    )

    assert first == second
    assert first.evidence_id.startswith("evidence-")
    assert first.artifact_id == "artifact-123"
    assert first.content_hash == "a" * 64
    assert first.value == 21488
    assert first.excerpt == "21488"
    assert first.as_of == "2026-07-12"
    assert first.source == "akshare"
    assert first.quality_grade == "normal"
    assert first.stale is False

    changed = build_evidence_ref(
        _descriptor(content_hash="b" * 64),
        payload,
        json_pointer="/total_funds",
        claim_type="market.total_funds",
    )
    assert changed.evidence_id != first.evidence_id


def test_finding_requires_at_least_one_evidence_reference():
    evidence = build_evidence_ref(
        _descriptor(),
        {"total_funds": 21488},
        json_pointer="/total_funds",
        claim_type="market.total_funds",
    )

    finding = build_finding(
        topic="market",
        category="breadth",
        label="基金总数",
        value=21488,
        evidence=(evidence,),
    )
    missing = build_finding(
        topic="market",
        category="breadth",
        label="基金总数",
        value=21488,
        evidence=(),
    )

    assert finding is not None
    assert finding.evidence_ids == (evidence.evidence_id,)
    assert finding.quality_grade == "normal"
    assert missing is None
