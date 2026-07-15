from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

from .mcp_adapter import MCP_TOOL_NAMES, McpAdapterError, ResearchMcpAdapter
from .mcp_gateway import McpToolGateway


class McpDependencyUnavailable(RuntimeError):
    pass


def create_mcp_server(
    output_dir: Path | str,
    *,
    timeout_seconds: float = 10.0,
    audit_path: Path | str | None = None,
):
    FastMCP, ToolError = _load_mcp_api()
    resolved_output_dir = Path(output_dir)
    resolved_audit_path = (
        Path(audit_path)
        if audit_path is not None
        else resolved_output_dir / "audit" / "mcp_calls.jsonl"
    )
    gateway = McpToolGateway(
        ResearchMcpAdapter(resolved_output_dir),
        audit_path=resolved_audit_path,
        audit_root=(
            resolved_output_dir if audit_path is None else resolved_audit_path.parent
        ),
        timeout_seconds=timeout_seconds,
    )
    server = FastMCP(
        "YA FundMind Research",
        json_response=True,
        instructions=(
            "Local read-only fund and ETF research tools. "
            "No trading, broker access, configuration writes, buy/sell advice, or guaranteed returns."
        ),
    )

    async def call(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            return await gateway.call(tool, arguments)
        except McpAdapterError as exc:
            raise ToolError(f"{exc.code}: {exc}") from exc

    @server.tool()
    async def status() -> dict[str, Any]:
        """Return local research artifact availability and immutable safety boundaries."""
        return await call("status", {})

    @server.tool()
    async def catalog(
        artifact_type: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """List only registered local research artifacts; arbitrary paths are not accepted."""
        return await call("catalog", {"artifact_type": artifact_type, "limit": limit})

    @server.tool()
    async def query(topic: str, code: str | None = None) -> dict[str, Any]:
        """Read a compact structured research context for an allowlisted topic."""
        arguments: dict[str, Any] = {"topic": topic}
        if code is not None:
            arguments["code"] = code
        return await call("query", arguments)

    @server.tool()
    async def ask(question: str) -> dict[str, Any]:
        """Answer a bounded research question with citations and transaction guardrails."""
        return await call("ask", {"question": question})

    @server.tool()
    async def evidence(topic: str, code: str | None = None) -> dict[str, Any]:
        """Build an evidence bundle with source hashes and JSON Pointer citations."""
        arguments: dict[str, Any] = {"topic": topic}
        if code is not None:
            arguments["code"] = code
        return await call("evidence", arguments)

    return server


def run_mcp_server(
    output_dir: Path | str,
    *,
    transport: str = "stdio",
    timeout_seconds: float = 10.0,
    audit_path: Path | str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    if transport not in {"stdio", "streamable-http"}:
        raise ValueError("transport must be stdio or streamable-http")
    server = create_mcp_server(
        output_dir,
        timeout_seconds=timeout_seconds,
        audit_path=audit_path,
    )
    if dry_run:
        return {
            "status": "ready",
            "transport": transport,
            "tools": list(MCP_TOOL_NAMES),
            "read_only": True,
        }
    server.run(transport=transport)
    return {
        "status": "stopped",
        "transport": transport,
        "tools": list(MCP_TOOL_NAMES),
        "read_only": True,
    }


def _load_mcp_api():
    try:
        fastmcp_module = import_module("mcp.server.fastmcp")
        errors_module = import_module("mcp.server.fastmcp.exceptions")
    except (ImportError, ModuleNotFoundError) as exc:
        raise McpDependencyUnavailable(
            "The optional MCP dependency is not installed; run pip install -e '.[mcp]'."
        ) from exc
    return fastmcp_module.FastMCP, errors_module.ToolError
