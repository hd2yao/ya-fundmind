from __future__ import annotations

import re
from typing import Any


_KEY_VALUE_SECRET = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|token|password|secret|cookie|authorization)"
    r"\s*[:=]\s*[^\s,;]+"
)
_BEARER_SECRET = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
_FILE_URL_PATH = re.compile(r"(?i)\bfile:///(?:[^\s,;]+)")
_WINDOWS_LOCAL_PATH = re.compile(r"(?i)(?<!\w)[a-z]:\\+(?:[^\s,;]+)")
_POSIX_LOCAL_PATH = re.compile(
    r"(?<![:\w])/(?:Users|home|private|var|tmp)(?:/[^\s,;]+)+"
)
_SENSITIVE_KEY_PARTS = frozenset(
    {
        "apikey",
        "accesstoken",
        "token",
        "password",
        "secret",
        "cookie",
        "authorization",
        "credential",
    }
)


def redact_text(value: str, *, limit: int | None = None) -> str:
    redacted = _KEY_VALUE_SECRET.sub(
        lambda match: f"{match.group(1)}=[REDACTED]", str(value)
    )
    redacted = _BEARER_SECRET.sub("Bearer [REDACTED]", redacted)
    redacted = _FILE_URL_PATH.sub("[PATH_REDACTED]", redacted)
    redacted = _WINDOWS_LOCAL_PATH.sub("[PATH_REDACTED]", redacted)
    redacted = _POSIX_LOCAL_PATH.sub("[PATH_REDACTED]", redacted)
    if limit is None or len(redacted) <= limit:
        return redacted
    if limit <= 3:
        return redacted[:limit]
    return f"{redacted[: limit - 3]}..."


def sanitize_data(value: Any, *, key: str | None = None) -> Any:
    if key is not None and _is_sensitive_key(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(item_key): sanitize_data(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [sanitize_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_data(item) for item in value)
    if isinstance(value, str):
        return redact_text(value)
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)
