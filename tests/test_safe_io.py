import json

import pytest

from fund_agent.safe_io import append_json_line


def test_append_json_line_allows_trusted_root_behind_symlink(tmp_path) -> None:
    real_root = tmp_path / "real-output"
    real_root.mkdir()
    trusted_alias = tmp_path / "output-alias"
    try:
        trusted_alias.symlink_to(real_root, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    destination = trusted_alias / "audit" / "events.jsonl"
    append_json_line(
        destination,
        {"status": "ok"},
        trusted_root=trusted_alias,
    )

    assert json.loads(destination.read_text(encoding="utf-8")) == {"status": "ok"}


def test_append_json_line_rejects_symlink_below_trusted_root(tmp_path) -> None:
    trusted_root = tmp_path / "outputs"
    trusted_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    audit_dir = trusted_root / "audit"
    try:
        audit_dir.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    with pytest.raises(OSError, match="symlink"):
        append_json_line(
            audit_dir / "events.jsonl",
            {"status": "blocked"},
            trusted_root=trusted_root,
        )

    assert not (outside / "events.jsonl").exists()


def test_append_json_line_rejects_destination_outside_trusted_root(tmp_path) -> None:
    trusted_root = tmp_path / "outputs"
    trusted_root.mkdir()

    with pytest.raises(OSError, match="trusted root"):
        append_json_line(
            tmp_path / "outside.jsonl",
            {"status": "blocked"},
            trusted_root=trusted_root,
        )

    assert not (tmp_path / "outside.jsonl").exists()
