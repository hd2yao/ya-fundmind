from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .agents import ResearchResult
from .models import ProviderHealth
from .snapshot import provider_health_to_dict

SCHEMA_VERSION = "1.0"
GENERATOR = "fund_agent"


def provider_trace_payload(result: ResearchResult, *, generated_at: str | None = None) -> dict:
    return provider_health_trace_payload(
        as_of=result.as_of,
        provider_health=result.provider_health,
        generated_at=generated_at,
    )


def provider_health_trace_payload(
    *,
    as_of: str,
    provider_health: tuple[ProviderHealth, ...],
    generated_at: str | None = None,
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or _generated_at(),
        "generator": GENERATOR,
        "as_of": as_of,
        "providers": [provider_health_to_dict(item) for item in provider_health],
    }


def write_provider_trace(
    result: ResearchResult,
    output_dir: Path | str,
    *,
    retention_days: int = 30,
    max_trace_files: int = 100,
    now: datetime | None = None,
) -> Path:
    return write_provider_health_trace(
        as_of=result.as_of,
        provider_health=result.provider_health,
        output_dir=output_dir,
        retention_days=retention_days,
        max_trace_files=max_trace_files,
        now=now,
    )


def write_provider_health_trace(
    *,
    as_of: str,
    provider_health: tuple[ProviderHealth, ...],
    output_dir: Path | str,
    filename_prefix: str = "provider",
    retention_days: int = 30,
    max_trace_files: int = 100,
    now: datetime | None = None,
) -> Path:
    resolved_now = _utc_now(now)
    trace_dir = Path(output_dir) / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    path = trace_dir / f"{filename_prefix}-{as_of}.json"
    path.write_text(
        json.dumps(
            provider_health_trace_payload(
                as_of=as_of,
                provider_health=provider_health,
                generated_at=resolved_now.isoformat(),
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    _prune_provider_traces(
        trace_dir,
        retention_days=retention_days,
        max_trace_files=max_trace_files,
        now=resolved_now,
    )
    return path


def _prune_provider_traces(
    trace_dir: Path,
    *,
    retention_days: int,
    max_trace_files: int,
    now: datetime,
) -> None:
    traces = sorted(trace_dir.glob("provider-*.json"), key=lambda item: item.stat().st_mtime)
    cutoff = now - timedelta(days=max(0, retention_days))
    for path in traces:
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if modified_at < cutoff:
            path.unlink(missing_ok=True)
    remaining = sorted(trace_dir.glob("provider-*.json"), key=lambda item: item.stat().st_mtime)
    overflow = max(0, len(remaining) - max(1, max_trace_files))
    for path in remaining[:overflow]:
        path.unlink(missing_ok=True)


def _generated_at() -> str:
    return _utc_now(None).isoformat()


def _utc_now(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
