from __future__ import annotations

import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Any

from . import __version__


_TRIGGER_PATTERN = re.compile(r"[^a-z0-9_.-]+")


def collect_runtime_provenance(
    *,
    cwd: Path | str | None = None,
    trigger: str | None = None,
) -> dict[str, Any]:
    working_dir = Path(cwd) if cwd is not None else Path.cwd()
    root_text = _git_text("rev-parse", "--show-toplevel", cwd=working_dir)
    git_root = Path(root_text) if root_text else working_dir
    commit = _git_text("rev-parse", "HEAD", cwd=git_root) if root_text else None
    status = _git_text("status", "--porcelain", cwd=git_root) if root_text else None
    return {
        "app_version": __version__,
        "git_commit": commit,
        "git_dirty": bool(status) if status is not None else None,
        "trigger": _normalize_trigger(trigger or os.environ.get("RUN_TRIGGER") or "manual"),
        "python_version": platform.python_version(),
    }


def _git_text(*arguments: str, cwd: Path | str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _normalize_trigger(value: str) -> str:
    normalized = _TRIGGER_PATTERN.sub("_", str(value).strip().lower()).strip("_")
    return normalized[:40] or "unknown"
