from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def append_json_line(path: Path | str, payload: dict[str, Any]) -> Path:
    resolved = Path(path)
    _reject_symlink_components(resolved)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(resolved)
    flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(resolved, flags, 0o600)
    except OSError as exc:
        if resolved.is_symlink():
            raise OSError(f"refusing symlink output path: {resolved}") from exc
        raise
    with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        handle.write("\n")
    return resolved


def _reject_symlink_components(path: Path) -> None:
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise OSError(f"refusing symlink output path: {candidate}")
