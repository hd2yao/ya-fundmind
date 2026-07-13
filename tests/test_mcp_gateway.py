import asyncio
import json
import time

import pytest

from fund_agent.mcp_adapter import McpAdapterError, ResearchMcpAdapter
from fund_agent.mcp_gateway import McpToolGateway


def test_gateway_returns_json_result_and_appends_success_audit(tmp_path) -> None:
    audit_path = tmp_path / "audit" / "mcp_calls.jsonl"
    gateway = McpToolGateway(
        ResearchMcpAdapter(tmp_path / "outputs"),
        audit_path=audit_path,
    )

    result = asyncio.run(gateway.call("status", {}))

    records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert result["tool"] == "status"
    assert result["metadata"]["read_only"] is True
    assert records[0]["tool"] == "status"
    assert records[0]["status"] == "ok"
    assert records[0]["duration_ms"] >= 0
    assert records[0]["result_status"] == "ok"


def test_gateway_redacts_question_and_secret_arguments(tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    gateway = McpToolGateway(
        ResearchMcpAdapter(tmp_path / "outputs"),
        audit_path=audit_path,
    )
    question = (
        "数据质量如何？ api_key=secret-123 password:hunter2 "
        "Bearer token-value Cookie=session-value"
    )

    asyncio.run(gateway.call("ask", {"question": question}))

    raw = audit_path.read_text(encoding="utf-8")
    record = json.loads(raw)
    assert "secret-123" not in raw
    assert "hunter2" not in raw
    assert "token-value" not in raw
    assert "session-value" not in raw
    assert record["argument_summary"]["question_hash"].startswith("sha256:")
    assert "[REDACTED]" in record["argument_summary"]["question_preview"]
    assert "question" not in record["argument_summary"]


def test_adapter_error_is_audited_and_preserves_safe_error_code(tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    gateway = McpToolGateway(
        ResearchMcpAdapter(tmp_path / "outputs"),
        audit_path=audit_path,
    )

    with pytest.raises(McpAdapterError) as exc_info:
        asyncio.run(gateway.call("query", {"topic": "invalid"}))

    record = json.loads(audit_path.read_text(encoding="utf-8"))
    assert exc_info.value.code == "invalid_argument"
    assert record["status"] == "error"
    assert record["error_code"] == "invalid_argument"
    assert "invalid" not in record["error_message"]


def test_unknown_tool_and_argument_names_cannot_smuggle_secrets_into_audit(tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    gateway = McpToolGateway(
        ResearchMcpAdapter(tmp_path / "outputs"),
        audit_path=audit_path,
    )

    with pytest.raises(McpAdapterError):
        asyncio.run(
            gateway.call(
                "token=tool-secret-123",
                {"topic": "market", "password-secret-456": "hidden"},
            )
        )

    raw = audit_path.read_text(encoding="utf-8")
    record = json.loads(raw)
    assert "tool-secret-123" not in raw
    assert "password-secret-456" not in raw
    assert record["tool"] == "[REDACTED]"
    assert record["argument_summary"]["unknown_argument_count"] == 1


class _SlowAdapter:
    def invoke(self, tool, arguments):
        time.sleep(0.05)
        return None


def test_timeout_is_classified_and_audited(tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    gateway = McpToolGateway(_SlowAdapter(), audit_path=audit_path, timeout_seconds=0.01)

    with pytest.raises(McpAdapterError) as exc_info:
        asyncio.run(gateway.call("status", {}))

    record = json.loads(audit_path.read_text(encoding="utf-8"))
    assert exc_info.value.code == "timeout"
    assert str(exc_info.value) == "Read-only research tool timed out."
    assert record["error_code"] == "timeout"


class _BrokenAdapter:
    def invoke(self, tool, arguments):
        raise RuntimeError("private path /Users/private/.env token=secret")


def test_unexpected_error_is_sanitized(tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    gateway = McpToolGateway(_BrokenAdapter(), audit_path=audit_path)

    with pytest.raises(McpAdapterError) as exc_info:
        asyncio.run(gateway.call("status", {}))

    raw = audit_path.read_text(encoding="utf-8")
    assert exc_info.value.code == "internal_error"
    assert str(exc_info.value) == "Read-only research tool failed."
    assert "/Users/private" not in raw
    assert "secret" not in raw


@pytest.mark.parametrize("timeout", (0, -1, 61, True, "10"))
def test_timeout_configuration_is_bounded(tmp_path, timeout) -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        McpToolGateway(
            ResearchMcpAdapter(tmp_path / "outputs"),
            audit_path=tmp_path / "audit.jsonl",
            timeout_seconds=timeout,
        )


def test_audit_is_append_only_for_multiple_calls(tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    gateway = McpToolGateway(
        ResearchMcpAdapter(tmp_path / "outputs"),
        audit_path=audit_path,
    )

    asyncio.run(gateway.call("status", {}))
    asyncio.run(gateway.call("catalog", {}))

    assert len(audit_path.read_text(encoding="utf-8").splitlines()) == 2
