from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .audit import append_research_audit
from .copilot_renderer import render_research_answer
from .models import ResearchAnswer


@dataclass(frozen=True)
class ResearchAnswerOutputs:
    json_path: Path
    markdown_path: Path
    audit_path: Path


def write_research_answer_outputs(
    answer: ResearchAnswer,
    output_dir: Path | str,
    *,
    json_path: Path | str | None = None,
    markdown_path: Path | str | None = None,
    audit_path: Path | str | None = None,
) -> ResearchAnswerOutputs:
    root = Path(output_dir)
    resolved_json = Path(json_path) if json_path else root / "copilot" / "research_answer.json"
    resolved_markdown = (
        Path(markdown_path) if markdown_path else root / "copilot" / "research_answer.md"
    )
    resolved_audit = Path(audit_path) if audit_path else root / "audit" / "research_queries.jsonl"
    resolved_json.parent.mkdir(parents=True, exist_ok=True)
    resolved_markdown.parent.mkdir(parents=True, exist_ok=True)
    resolved_json.write_text(
        json.dumps(asdict(answer), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    resolved_markdown.write_text(render_research_answer(answer), encoding="utf-8")
    append_research_audit(answer, resolved_audit, output_path=resolved_json)
    return ResearchAnswerOutputs(
        json_path=resolved_json,
        markdown_path=resolved_markdown,
        audit_path=resolved_audit,
    )
