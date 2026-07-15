from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .artifacts import ARTIFACT_PATTERNS, ArtifactCatalog
from .models import McpToolResult
from .redaction import sanitize_data
from .research_copilot import ResearchCopilot
from .research_evidence import build_evidence_bundle
from .research_query import (
    SUPPORTED_RESEARCH_TOPICS,
    TOPIC_ARTIFACT_TYPES,
    ResearchQueryService,
)


MCP_TOOL_NAMES = ("status", "catalog", "query", "ask", "evidence")
_ARTIFACT_TYPES = frozenset(item[0] for item in ARTIFACT_PATTERNS)
_FUND_CODE = re.compile(r"\d{6}")
_ALLOWED_ARGUMENTS = {
    "status": frozenset(),
    "catalog": frozenset({"artifact_type", "limit"}),
    "query": frozenset({"topic", "code"}),
    "ask": frozenset({"question"}),
    "evidence": frozenset({"topic", "code"}),
}


class McpAdapterError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class ResearchMcpAdapter:
    def __init__(self, output_dir: Path | str):
        self.output_dir = Path(output_dir).resolve()
        self.catalog = ArtifactCatalog(self.output_dir)
        self.query_service = ResearchQueryService(self.output_dir)
        self.copilot = ResearchCopilot(self.output_dir, query_service=self.query_service)

    def invoke(self, tool: str, arguments: dict[str, Any] | None = None) -> McpToolResult:
        tool_name = str(tool or "")
        if tool_name not in MCP_TOOL_NAMES:
            raise McpAdapterError("unsupported_tool", "Unsupported read-only research tool.")
        payload = dict(arguments or {})
        if set(payload) - _ALLOWED_ARGUMENTS[tool_name]:
            raise McpAdapterError("invalid_argument", "Tool arguments are not allowed.")
        if tool_name == "status":
            return self._status()
        if tool_name == "catalog":
            return self._catalog(payload)
        if tool_name == "query":
            return self._query(payload)
        if tool_name == "ask":
            return self._ask(payload)
        return self._evidence(payload)

    def _status(self) -> McpToolResult:
        descriptors = self.catalog.scan()
        present_types = {item.artifact_type for item in descriptors}
        available_topics = [
            topic
            for topic in SUPPORTED_RESEARCH_TOPICS
            if present_types.intersection(TOPIC_ARTIFACT_TYPES[topic])
        ]
        as_of_values = sorted(item.as_of for item in descriptors if item.as_of)
        return self._result(
            "status",
            status="ok",
            data={
                "service": "ya-fundmind-research",
                "artifact_count": len(descriptors),
                "artifact_types": sorted(present_types),
                "available_topics": available_topics,
                "latest_as_of": as_of_values[-1] if as_of_values else None,
                "tools": list(MCP_TOOL_NAMES),
                "boundaries": {
                    "read_only": True,
                    "trading": False,
                    "broker_access": False,
                    "buy_sell_advice": False,
                },
            },
            warnings=tuple(
                dict.fromkeys(
                    warning
                    for descriptor in descriptors
                    for warning in descriptor.warnings
                )
            ),
        )

    def _catalog(self, arguments: dict[str, Any]) -> McpToolResult:
        artifact_type = arguments.get("artifact_type")
        if artifact_type is not None and (
            not isinstance(artifact_type, str) or artifact_type not in _ARTIFACT_TYPES
        ):
            raise McpAdapterError("invalid_argument", "Invalid artifact type.")
        limit = arguments.get("limit", 100)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise McpAdapterError("invalid_argument", "Invalid catalog limit.")
        descriptors = (
            self.catalog.find(artifact_type=artifact_type)
            if artifact_type is not None
            else self.catalog.scan()
        )
        selected = descriptors[:limit]
        return self._result(
            "catalog",
            status="ok",
            data={
                "artifacts": [asdict(item) for item in selected],
                "returned_count": len(selected),
                "total_count": len(descriptors),
                "truncated": len(selected) < len(descriptors),
            },
            warnings=tuple(
                dict.fromkeys(
                    warning
                    for descriptor in selected
                    for warning in descriptor.warnings
                )
            ),
        )

    def _query(self, arguments: dict[str, Any]) -> McpToolResult:
        topic, code = _validated_topic_code(arguments)
        context = self.query_service.query(topic, code=code)
        return self._result(
            "query",
            status=context.status,
            data=asdict(context),
            warnings=context.warnings,
        )

    def _ask(self, arguments: dict[str, Any]) -> McpToolResult:
        question = arguments.get("question")
        if not isinstance(question, str) or not question.strip() or len(question) > 1000:
            raise McpAdapterError("invalid_argument", "Invalid research question.")
        answer = self.copilot.answer(question)
        return self._result(
            "ask",
            status=answer.answer_status,
            data=asdict(answer),
            warnings=answer.warnings,
        )

    def _evidence(self, arguments: dict[str, Any]) -> McpToolResult:
        topic, code = _validated_topic_code(arguments)
        context = self.query_service.query(topic, code=code)
        if context.status == "unavailable":
            return self._result(
                "evidence",
                status="unavailable",
                data={"context": asdict(context), "bundle": None},
                warnings=context.warnings,
            )
        bundle = build_evidence_bundle(context, self.output_dir)
        return self._result(
            "evidence",
            status=bundle.status,
            data=asdict(bundle),
            warnings=bundle.warnings,
        )

    @staticmethod
    def _result(
        tool: str,
        *,
        status: str,
        data: dict[str, Any],
        warnings: tuple[str, ...] = (),
    ) -> McpToolResult:
        return McpToolResult(
            schema_version="1.0",
            generated_at=datetime.now(timezone.utc).isoformat(),
            generator="fund_agent",
            tool=tool,
            status=status,
            data=sanitize_data(json.loads(json.dumps(data, ensure_ascii=False))),
            warnings=tuple(dict.fromkeys(sanitize_data(warnings))),
            metadata={
                "read_only": True,
                "not_production_model": True,
                "main_score_changed": False,
                "main_risk_changed": False,
            },
        )


def _validated_topic_code(arguments: dict[str, Any]) -> tuple[str, str | None]:
    topic = arguments.get("topic")
    if topic not in SUPPORTED_RESEARCH_TOPICS:
        raise McpAdapterError("invalid_argument", "Invalid research topic.")
    code = arguments.get("code")
    if code is None:
        return str(topic), None
    if topic != "fund" or not isinstance(code, str) or _FUND_CODE.fullmatch(code) is None:
        raise McpAdapterError("invalid_argument", "Invalid fund code argument.")
    return str(topic), code
