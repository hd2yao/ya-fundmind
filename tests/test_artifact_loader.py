from dataclasses import replace
import json
from pathlib import Path

from fund_agent.artifacts import ArtifactCatalog, ArtifactLoader


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_loader_reads_registered_json_and_ignores_unknown_optional_fields(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(
        output_dir / "fund_agent_report.json",
        {"schema_version": "1.0", "as_of": "2026-07-12", "future_optional": {"x": 1}},
    )
    descriptor = ArtifactCatalog(output_dir).scan()[0]

    result = ArtifactLoader(output_dir).load(descriptor)

    assert result.status == "ok"
    assert result.payload["future_optional"] == {"x": 1}
    assert result.warnings == ()


def test_loader_reports_missing_file_after_catalog_scan(tmp_path):
    output_dir = tmp_path / "outputs"
    path = output_dir / "ops_status.json"
    _write_json(path, {"generated_at": "2026-07-12T00:00:00+00:00"})
    descriptor = ArtifactCatalog(output_dir).scan()[0]
    path.unlink()

    result = ArtifactLoader(output_dir).load(descriptor)

    assert result.status == "missing"
    assert result.payload is None
    assert result.warnings == ("artifact_missing",)


def test_loader_reports_invalid_json_and_non_object_roots(tmp_path):
    output_dir = tmp_path / "outputs"
    invalid = output_dir / "news" / "news_evidence_report.json"
    invalid.parent.mkdir(parents=True)
    invalid.write_text("{invalid", encoding="utf-8")
    _write_json(output_dir / "portfolio" / "portfolio_report.json", [1, 2, 3])
    descriptors = {item.artifact_type: item for item in ArtifactCatalog(output_dir).scan()}
    loader = ArtifactLoader(output_dir)

    invalid_result = loader.load(descriptors["news_evidence"])
    shape_result = loader.load(descriptors["portfolio_report"])

    assert invalid_result.status == "invalid_json"
    assert invalid_result.payload is None
    assert invalid_result.warnings == ("invalid_json",)
    assert shape_result.status == "invalid_shape"
    assert shape_result.payload is None
    assert shape_result.warnings == ("invalid_json_root",)


def test_loader_accepts_legacy_payload_without_schema_with_warning(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(output_dir / "daily_research_summary.json", {"as_of": "2026-07-12", "status": "success"})
    descriptor = ArtifactCatalog(output_dir).scan()[0]

    result = ArtifactLoader(output_dir).load(descriptor)

    assert result.status == "ok"
    assert result.payload["status"] == "success"
    assert result.warnings == ("schema_version_missing",)


def test_loader_blocks_path_traversal_and_unregistered_paths(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(output_dir / "ops_status.json", {"schema_version": "1.0"})
    _write_json(tmp_path / "outside.json", {"private": True})
    descriptor = ArtifactCatalog(output_dir).scan()[0]
    loader = ArtifactLoader(output_dir)

    traversal = loader.load(replace(descriptor, path="../outside.json"))
    unregistered = loader.load(replace(descriptor, path="arbitrary.json"))

    assert traversal.status == "blocked"
    assert traversal.payload is None
    assert traversal.warnings == ("artifact_path_outside_output_dir",)
    assert unregistered.status == "blocked"
    assert unregistered.warnings == ("artifact_not_registered",)
