from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def append_json_line(
    path: Path | str,
    payload: dict[str, Any],
    *,
    trusted_root: Path | str | None = None,
) -> Path:
    destination = Path(path)
    absolute_destination = _absolute_path(destination)
    absolute_root = _absolute_path(trusted_root or destination.parent)
    _reject_unsafe_components(absolute_destination, absolute_root)
    absolute_destination.parent.mkdir(parents=True, exist_ok=True)
    _reject_unsafe_components(absolute_destination, absolute_root)
    flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(absolute_destination, flags, 0o600)
    except OSError as exc:
        if absolute_destination.is_symlink():
            raise OSError(
                f"refusing symlink output path: {absolute_destination}"
            ) from exc
        raise
    with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        handle.write("\n")
    return destination


def _absolute_path(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _reject_unsafe_components(path: Path, trusted_root: Path) -> None:
    try:
        relative = path.relative_to(trusted_root)
    except ValueError as exc:
        raise OSError("refusing output path outside trusted root") from exc
    if not relative.parts:
        raise OSError("refusing output path equal to trusted root")

    candidate = trusted_root
    for part in relative.parts:
        candidate /= part
        if candidate.is_symlink():
            raise OSError(f"refusing symlink output path: {candidate}")
