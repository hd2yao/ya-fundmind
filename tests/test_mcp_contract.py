import json
from dataclasses import asdict

from fund_agent.cli import main
from fund_agent.contract import validate_contract_file
from fund_agent.mcp_adapter import ResearchMcpAdapter


def test_mcp_tool_result_contract_accepts_structured_adapter_output(tmp_path) -> None:
    result = ResearchMcpAdapter(tmp_path / "outputs").invoke("status", {})
    path = tmp_path / "mcp-result.json"
    path.write_text(json.dumps(asdict(result)), encoding="utf-8")

    validation = validate_contract_file(path, "mcp_tool_result")

    assert validation.ok is True
    assert main(["validate-contract", "--mcp-result", str(path)]) == 0


def test_mcp_tool_result_contract_rejects_write_tool_and_mutable_boundary(tmp_path) -> None:
    path = tmp_path / "invalid-mcp-result.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "generated_at": "2026-07-13T00:00:00+00:00",
                "generator": "fund_agent",
                "tool": "write_config",
                "status": "ok",
                "data": {},
                "warnings": [],
                "metadata": {"read_only": False},
            }
        ),
        encoding="utf-8",
    )

    validation = validate_contract_file(path, "mcp_tool_result")

    assert validation.ok is False
    assert any("Unsupported MCP tool" in error for error in validation.errors)
    assert any("read_only" in error for error in validation.errors)
