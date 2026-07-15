import json

from fund_agent.cli import _write_run_metadata
from fund_agent.runtime_provenance import collect_runtime_provenance


def test_collect_runtime_provenance_records_version_commit_dirty_and_trigger(
    monkeypatch, tmp_path
) -> None:
    values = {
        ("rev-parse", "--show-toplevel"): str(tmp_path),
        ("rev-parse", "HEAD"): "a" * 40,
        ("status", "--porcelain"): " M tracked.py",
    }
    monkeypatch.setattr(
        "fund_agent.runtime_provenance._git_text",
        lambda *args, **kwargs: values.get(tuple(args)),
    )
    monkeypatch.setenv("RUN_TRIGGER", "launchd")

    provenance = collect_runtime_provenance(cwd=tmp_path)

    assert provenance["app_version"]
    assert provenance["git_commit"] == "a" * 40
    assert provenance["git_dirty"] is True
    assert provenance["trigger"] == "launchd"
    assert provenance["python_version"]


def test_run_metadata_embeds_runtime_provenance(monkeypatch, tmp_path) -> None:
    expected = {
        "app_version": "2.0.0rc1",
        "git_commit": "a" * 40,
        "git_dirty": False,
        "trigger": "daily_ops",
        "python_version": "3.12.0",
    }
    monkeypatch.setattr(
        "fund_agent.cli.collect_runtime_provenance",
        lambda: expected,
        raising=False,
    )
    run_dir = tmp_path / "runs" / "2026-07-12"
    run_dir.mkdir(parents=True)

    _write_run_metadata(
        run_dir,
        as_of="2026-07-12",
        started_at="2026-07-12T13:30:00+00:00",
        finished_at="2026-07-12T13:31:00+00:00",
        duration_ms=60000,
        steps=(),
        status="success",
    )

    payload = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert payload["generated_at"] == "2026-07-12T13:31:00+00:00"
    assert payload["generator"] == "fund_agent"
    assert payload["provenance"] == expected
