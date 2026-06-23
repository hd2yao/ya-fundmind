from __future__ import annotations

import json
from pathlib import Path

from .agents import ResearchResult
from .snapshot import _provider_health_to_dict


def provider_trace_payload(result: ResearchResult) -> dict:
    return {
        "as_of": result.as_of,
        "providers": [_provider_health_to_dict(item) for item in result.provider_health],
    }


def write_provider_trace(result: ResearchResult, output_dir: Path | str) -> Path:
    trace_dir = Path(output_dir) / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    path = trace_dir / f"provider-{result.as_of}.json"
    path.write_text(
        json.dumps(provider_trace_payload(result), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path
