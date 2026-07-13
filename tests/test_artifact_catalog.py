import json
from pathlib import Path

from fund_agent.artifacts import ArtifactCatalog


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_catalog_discovers_only_registered_artifacts_with_metadata(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(
        output_dir / "fund_agent_report.json",
        {
            "schema_version": "1.0",
            "as_of": "2026-07-12",
            "generated_at": "2026-07-12T13:00:00+00:00",
            "data_quality_grade": "normal",
            "source": "akshare",
            "stale": False,
        },
    )
    _write_json(
        output_dir / "snapshots" / "2026-07-12.json",
        {
            "schema_version": "1.0",
            "as_of": "2026-07-12",
            "generated_at": "2026-07-12T13:00:00+00:00",
        },
    )
    _write_json(output_dir / "unregistered.json", {"secret": "not catalogued"})

    catalog = ArtifactCatalog(output_dir)
    descriptors = catalog.scan()

    assert [item.artifact_type for item in descriptors] == ["report", "snapshot"]
    report = descriptors[0]
    assert report.path == "fund_agent_report.json"
    assert report.schema_version == "1.0"
    assert report.as_of == "2026-07-12"
    assert report.generated_at == "2026-07-12T13:00:00+00:00"
    assert report.source == "akshare"
    assert report.quality_grade == "normal"
    assert report.stale is False
    assert report.artifact_id.startswith("artifact-")
    assert len(report.content_hash) == 64
    assert report.warnings == ()


def test_catalog_ids_and_hashes_are_stable_and_find_filters_by_type(tmp_path):
    output_dir = tmp_path / "outputs"
    snapshot = output_dir / "snapshots" / "2026-07-11.json"
    _write_json(snapshot, {"as_of": "2026-07-11", "value": 1})

    catalog = ArtifactCatalog(output_dir)
    first = catalog.scan()[0]
    second = catalog.scan()[0]

    assert first.artifact_id == second.artifact_id
    assert first.content_hash == second.content_hash
    assert catalog.find(artifact_type="snapshot") == (second,)
    assert catalog.find(artifact_type="report") == ()

    _write_json(snapshot, {"as_of": "2026-07-11", "value": 2})
    changed = catalog.scan()[0]
    assert changed.artifact_id == first.artifact_id
    assert changed.content_hash != first.content_hash


def test_catalog_records_invalid_json_without_aborting_other_artifacts(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(output_dir / "ops_status.json", {"generated_at": "2026-07-12T00:00:00+00:00"})
    invalid = output_dir / "news" / "news_evidence_report.json"
    invalid.parent.mkdir(parents=True)
    invalid.write_text("{invalid", encoding="utf-8")

    descriptors = ArtifactCatalog(output_dir).scan()

    assert [item.artifact_type for item in descriptors] == ["news_evidence", "ops_status"]
    news = descriptors[0]
    assert news.schema_version is None
    assert news.as_of is None
    assert news.warnings == ("invalid_json",)


def test_catalog_does_not_follow_symlinks_outside_output_dir(tmp_path):
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    outside = tmp_path / "outside.json"
    _write_json(outside, {"schema_version": "1.0", "private": True})
    (output_dir / "ops_status.json").symlink_to(outside)

    assert ArtifactCatalog(output_dir).scan() == ()


def test_catalog_derives_nested_quality_stale_and_provider_source(tmp_path):
    output_dir = tmp_path / "outputs"
    _write_json(
        output_dir / "fund_agent_report.json",
        {
            "schema_version": "1.0",
            "as_of": "2026-07-12",
            "provider_health": [
                {
                    "provider": "akshare",
                    "warnings": [{"code": "stale_cache", "severity": "warning"}],
                }
            ],
            "data_quality_summary": {"grade": "warning"},
        },
    )

    descriptor = ArtifactCatalog(output_dir).scan()[0]

    assert descriptor.source == "akshare"
    assert descriptor.quality_grade == "warning"
    assert descriptor.stale is True
