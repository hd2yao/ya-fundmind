from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from .audit import redact_preview
from .mcp_adapter import MCP_TOOL_NAMES, McpAdapterError
from .safe_io import append_json_line


_AUDIT_ARGUMENTS = frozenset({"topic", "code", "question", "artifact_type", "limit"})


class McpToolGateway:
    def __init__(
        self,
        adapter: Any,
        *,
        audit_path: Path | str,
        audit_root: Path | str | None = None,
        timeout_seconds: float = 10.0,
    ):
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not 0 < timeout_seconds <= 60
        ):
            raise ValueError("timeout_seconds must be greater than 0 and at most 60")
        self.adapter = adapter
        self.audit_path = Path(audit_path)
        self.audit_root = Path(audit_root) if audit_root is not None else self.audit_path.parent
        self.timeout_seconds = float(timeout_seconds)

    async def call(
        self,
        tool: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        started = perf_counter()
        payload = dict(arguments or {})
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(self.adapter.invoke, tool, payload),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            error = McpAdapterError("timeout", "Read-only research tool timed out.")
            self._record_or_raise(tool, payload, started, error=error)
            raise error from exc
        except McpAdapterError as exc:
            self._record_or_raise(tool, payload, started, error=exc)
            raise
        except Exception as exc:
            error = McpAdapterError("internal_error", "Read-only research tool failed.")
            self._record_or_raise(tool, payload, started, error=error)
            raise error from exc

        result_payload = json.loads(json.dumps(asdict(result), ensure_ascii=False))
        self._record_or_raise(tool, payload, started, result=result_payload)
        return result_payload

    def _record_or_raise(
        self,
        tool: str,
        arguments: dict[str, Any],
        started: float,
        *,
        result: dict[str, Any] | None = None,
        error: McpAdapterError | None = None,
    ) -> None:
        try:
            self._append_audit(tool, arguments, started, result=result, error=error)
        except OSError as exc:
            raise McpAdapterError(
                "audit_unavailable",
                "Research tool audit is unavailable.",
            ) from exc

    def _append_audit(
        self,
        tool: str,
        arguments: dict[str, Any],
        started: float,
        *,
        result: dict[str, Any] | None = None,
        error: McpAdapterError | None = None,
    ) -> None:
        generated_at = datetime.now(timezone.utc).isoformat()
        record = {
            "schema_version": "1.0",
            "generated_at": generated_at,
            "generator": "fund_agent",
            "timestamp": generated_at,
            "tool": str(tool) if tool in MCP_TOOL_NAMES else "[REDACTED]",
            "status": "error" if error is not None else "ok",
            "duration_ms": max(0, int((perf_counter() - started) * 1000)),
            "timeout_seconds": self.timeout_seconds,
            "argument_summary": _argument_summary(arguments),
            "result_status": (result or {}).get("status"),
            "result_counts": _result_counts(result),
            "error_code": error.code if error is not None else None,
            "error_message": str(error) if error is not None else None,
        }
        append_json_line(self.audit_path, record, trusted_root=self.audit_root)


def _argument_summary(arguments: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    question = arguments.get("question")
    if isinstance(question, str):
        summary["question_hash"] = f"sha256:{hashlib.sha256(question.encode('utf-8')).hexdigest()}"
        summary["question_preview"] = redact_preview(question)
    unknown_count = len(set(arguments) - _AUDIT_ARGUMENTS)
    if unknown_count:
        summary["unknown_argument_count"] = unknown_count
    for key, value in arguments.items():
        if key not in _AUDIT_ARGUMENTS:
            continue
        if key == "question":
            continue
        normalized_key = str(key).lower()
        if any(secret in normalized_key for secret in ("token", "password", "secret", "cookie", "key")):
            summary[str(key)] = "[REDACTED]"
        elif isinstance(value, str):
            summary[str(key)] = redact_preview(value, limit=80)
        elif isinstance(value, (int, float, bool)) or value is None:
            summary[str(key)] = value
        else:
            summary[str(key)] = f"<{type(value).__name__}>"
    return summary


def _result_counts(result: dict[str, Any] | None) -> dict[str, int]:
    if not result:
        return {}
    data = result.get("data")
    if not isinstance(data, dict):
        return {}
    counts: dict[str, int] = {}
    for field in ("artifacts", "findings", "evidence", "data_gaps", "warnings"):
        value = data.get(field)
        if isinstance(value, list):
            counts[field] = len(value)
    return counts
