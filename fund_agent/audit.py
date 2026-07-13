from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ResearchAnswer


_KEY_VALUE_SECRET = re.compile(
    r"(?i)\b(api[_-]?key|token|password|secret|cookie)\s*[:=]\s*[^\s,;]+"
)
_BEARER_SECRET = re.compile(r"(?i)\bbearer\s+[^\s,;]+")


def append_research_audit(
    answer: ResearchAnswer,
    audit_path: Path | str,
    *,
    output_path: Path | str | None = None,
) -> Path:
    path = Path(audit_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(answer)
    question = str(payload.get("question") or "")
    record: dict[str, Any] = {
        "schema_version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question_hash": f"sha256:{hashlib.sha256(question.encode('utf-8')).hexdigest()}",
        "question_preview": redact_preview(question),
        "intent": (payload.get("intent") or {}).get("intent"),
        "answer_status": payload.get("answer_status"),
        "finding_count": len(payload.get("findings") or []),
        "evidence_count": len(payload.get("evidence") or []),
        "data_gap_count": len(payload.get("data_gaps") or []),
        "warning_count": len(payload.get("warnings") or []),
        "review_required": bool(payload.get("review_required")),
        "output_path": str(output_path) if output_path is not None else None,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
        handle.write("\n")
    return path


def redact_preview(question: str, *, limit: int = 160) -> str:
    redacted = _KEY_VALUE_SECRET.sub(lambda match: f"{match.group(1)}=[REDACTED]", question)
    redacted = _BEARER_SECRET.sub("Bearer [REDACTED]", redacted)
    if len(redacted) <= limit:
        return redacted
    return f"{redacted[: limit - 3]}..."
