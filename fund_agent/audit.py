from __future__ import annotations

import hashlib
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ResearchAnswer
from .redaction import redact_text
from .safe_io import append_json_line


def append_research_audit(
    answer: ResearchAnswer,
    audit_path: Path | str,
    *,
    output_path: Path | str | None = None,
    trusted_root: Path | str | None = None,
) -> Path:
    path = Path(audit_path)
    payload = asdict(answer)
    question = str(payload.get("question") or "")
    generated_at = datetime.now(timezone.utc).isoformat()
    record: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at": generated_at,
        "generator": "fund_agent",
        "timestamp": generated_at,
        "question_hash": f"sha256:{hashlib.sha256(question.encode('utf-8')).hexdigest()}",
        "question_preview": redact_preview(question),
        "intent": (payload.get("intent") or {}).get("intent"),
        "answer_status": payload.get("answer_status"),
        "finding_count": len(payload.get("findings") or []),
        "evidence_count": len(payload.get("evidence") or []),
        "data_gap_count": len(payload.get("data_gaps") or []),
        "warning_count": len(payload.get("warnings") or []),
        "review_required": bool(payload.get("review_required")),
        "output_path": (
            redact_preview(Path(output_path).name, limit=120)
            if output_path is not None
            else None
        ),
    }
    return append_json_line(path, record, trusted_root=trusted_root)


def redact_preview(question: str, *, limit: int = 160) -> str:
    return redact_text(question, limit=limit)
