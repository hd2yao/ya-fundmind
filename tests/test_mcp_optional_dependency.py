import asyncio
from pathlib import Path

import pytest

import fund_agent.mcp_server as mcp_server
from fund_agent.mcp_server import McpDependencyUnavailable, create_mcp_server, run_mcp_server


class _FakeToolError(RuntimeError):
    pass


class _FakeFastMCP:
    def __init__(self, name, **kwargs):
        self.name = name
        self.kwargs = kwargs
        self.tools = {}
        self.run_calls = []

    def tool(self):
        def decorator(function):
            self.tools[function.__name__] = function
            return function

        return decorator

    def run(self, *, transport):
        self.run_calls.append(transport)


def test_missing_mcp_dependency_has_clear_error(monkeypatch, tmp_path) -> None:
    def missing(name):
        raise ModuleNotFoundError("mcp is not installed")

    monkeypatch.setattr(mcp_server, "import_module", missing)

    with pytest.raises(McpDependencyUnavailable) as exc_info:
        create_mcp_server(tmp_path / "outputs")

    assert "optional MCP dependency" in str(exc_info.value)
    assert "pip install -e '.[mcp]'" in str(exc_info.value)


def test_create_server_registers_exact_readonly_tool_allowlist(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        mcp_server,
        "_load_mcp_api",
        lambda: (_FakeFastMCP, _FakeToolError),
    )

    server = create_mcp_server(tmp_path / "outputs")

    assert set(server.tools) == {"status", "catalog", "query", "ask", "evidence"}
    assert server.kwargs["json_response"] is True
    assert "read-only" in server.kwargs["instructions"].lower()
    status = asyncio.run(server.tools["status"]())
    assert status["metadata"]["read_only"] is True


def test_server_maps_adapter_errors_to_tool_error(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        mcp_server,
        "_load_mcp_api",
        lambda: (_FakeFastMCP, _FakeToolError),
    )
    server = create_mcp_server(tmp_path / "outputs")

    with pytest.raises(_FakeToolError, match="invalid_argument"):
        asyncio.run(server.tools["query"]("invalid", None))


def test_run_server_dry_run_does_not_start_transport(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        mcp_server,
        "_load_mcp_api",
        lambda: (_FakeFastMCP, _FakeToolError),
    )

    result = run_mcp_server(tmp_path / "outputs", transport="stdio", dry_run=True)

    assert result["status"] == "ready"
    assert result["transport"] == "stdio"
    assert result["tools"] == ["status", "catalog", "query", "ask", "evidence"]


def test_run_server_uses_selected_transport(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        mcp_server,
        "_load_mcp_api",
        lambda: (_FakeFastMCP, _FakeToolError),
    )

    result = run_mcp_server(tmp_path / "outputs", transport="streamable-http")

    assert result["status"] == "stopped"
    assert result["transport"] == "streamable-http"
