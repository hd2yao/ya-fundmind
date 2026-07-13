import json

import pytest


pytest.importorskip("mcp", reason="optional MCP dependency is not installed")

from mcp.shared.memory import create_connected_server_and_client_session

from fund_agent.mcp_server import create_mcp_server


def _write_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_official_in_memory_client_lists_and_calls_readonly_tools(tmp_path) -> None:
    _write_json(
        tmp_path / "ops_status.json",
        {"schema_version": "1.0", "generated_at": "2026-07-13T00:00:00+00:00"},
    )
    app = create_mcp_server(tmp_path)

    async with create_connected_server_and_client_session(app, raise_exceptions=True) as session:
        tools = await session.list_tools()
        result = await session.call_tool("status", {})

    assert {tool.name for tool in tools.tools} == {
        "status",
        "catalog",
        "query",
        "ask",
        "evidence",
    }
    assert result.isError is False
    assert result.structuredContent["tool"] == "status"
    assert result.structuredContent["metadata"]["read_only"] is True
