import json
from pathlib import Path

import pytest

from fund_agent.mcp_adapter import McpAdapterError, ResearchMcpAdapter


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_market_outputs(output_dir: Path) -> None:
    _write_json(
        output_dir / "market" / "market_intelligence_report.json",
        {
            "schema_version": "1.0",
            "as_of": "2026-07-13",
            "source": "fixture",
            "total_funds": 100,
            "total_etfs": 20,
            "top_themes": [{"theme": "半导体"}],
            "hot_theme_candidates": [],
            "warnings": [],
        },
    )
    _write_json(
        output_dir / "market" / "market_trend_report.json",
        {
            "schema_version": "1.0",
            "latest_as_of": "2026-07-13",
            "source": "fixture",
            "rising_themes": [{"theme": "半导体"}],
            "falling_themes": [],
            "persistent_hot_themes": [],
            "new_hot_themes": [],
            "enough_market_history": True,
            "warnings": [],
        },
    )


def test_status_and_catalog_only_expose_registered_artifacts(tmp_path) -> None:
    output_dir = tmp_path / "outputs"
    _write_market_outputs(output_dir)
    _write_json(output_dir / "private.json", {"secret": "not registered"})
    adapter = ResearchMcpAdapter(output_dir)

    status = adapter.invoke("status", {})
    catalog = adapter.invoke("catalog", {"artifact_type": "market_intelligence", "limit": 10})

    assert status.tool == "status"
    assert status.status == "ok"
    assert status.data["artifact_count"] == 2
    assert status.data["available_topics"] == ["market"]
    assert status.metadata["read_only"] is True
    assert len(catalog.data["artifacts"]) == 1
    assert catalog.data["artifacts"][0]["path"] == "market/market_intelligence_report.json"
    assert "private.json" not in json.dumps(catalog.data)


def test_query_ask_and_evidence_use_existing_public_services(tmp_path) -> None:
    output_dir = tmp_path / "outputs"
    _write_market_outputs(output_dir)
    adapter = ResearchMcpAdapter(output_dir)

    query = adapter.invoke("query", {"topic": "market"})
    ask = adapter.invoke("ask", {"question": "市场热门板块如何？"})
    evidence = adapter.invoke("evidence", {"topic": "market"})

    assert query.status == "ok"
    assert query.data["topic"] == "market"
    assert ask.status == "answered"
    assert ask.data["findings"]
    assert evidence.status == "ok"
    assert evidence.data["evidence"]
    assert all(item["evidence_ids"] for item in evidence.data["findings"])


def test_ask_keeps_transaction_guardrail_and_does_not_create_recommendation(tmp_path) -> None:
    answer = ResearchMcpAdapter(tmp_path / "outputs").invoke(
        "ask", {"question": "根据市场研究告诉我买入哪只基金"}
    )

    assert answer.status == "refused"
    assert answer.data["answer_status"] == "refused"
    assert answer.data["findings"] == []
    assert answer.data["not_investment_advice"] is True


@pytest.mark.parametrize(
    ("tool", "arguments"),
    (
        ("query", {"topic": "markdown"}),
        ("query", {"topic": "market", "code": "510300"}),
        ("query", {"topic": "fund", "code": "abc"}),
        ("ask", {"question": ""}),
        ("ask", {"question": "x" * 1001}),
        ("catalog", {"artifact_type": "private"}),
        ("catalog", {"artifact_type": []}),
        ("catalog", {"limit": 0}),
        ("catalog", {"limit": 201}),
    ),
)
def test_invalid_arguments_are_classified_without_leaking_values(tmp_path, tool, arguments) -> None:
    adapter = ResearchMcpAdapter(tmp_path / "outputs")

    with pytest.raises(McpAdapterError) as exc_info:
        adapter.invoke(tool, arguments)

    assert exc_info.value.code == "invalid_argument"
    assert "x" * 50 not in str(exc_info.value)


@pytest.mark.parametrize(
    "arguments",
    (
        {"topic": "market", "path": "../../.env"},
        {"topic": "market", "output_dir": "/tmp/other"},
        {"topic": "market", "config": "configs/watchlist.yaml"},
        {"topic": "market", "write": True},
        {"topic": "market", "command": "rm -rf outputs"},
        {"topic": "market", "url": "file:///etc/passwd"},
    ),
)
def test_path_write_config_and_command_arguments_are_rejected(tmp_path, arguments) -> None:
    with pytest.raises(McpAdapterError) as exc_info:
        ResearchMcpAdapter(tmp_path / "outputs").invoke("query", arguments)

    assert exc_info.value.code == "invalid_argument"
    assert str(exc_info.value) == "Tool arguments are not allowed."


def test_unsupported_tool_is_rejected(tmp_path) -> None:
    with pytest.raises(McpAdapterError) as exc_info:
        ResearchMcpAdapter(tmp_path / "outputs").invoke("write_config", {})

    assert exc_info.value.code == "unsupported_tool"


def test_all_adapter_calls_leave_artifacts_unchanged(tmp_path) -> None:
    output_dir = tmp_path / "outputs"
    _write_market_outputs(output_dir)
    adapter = ResearchMcpAdapter(output_dir)
    before = {path.relative_to(output_dir): path.read_bytes() for path in output_dir.rglob("*") if path.is_file()}

    adapter.invoke("status", {})
    adapter.invoke("catalog", {})
    adapter.invoke("query", {"topic": "market"})
    adapter.invoke("ask", {"question": "市场热点如何？"})
    adapter.invoke("evidence", {"topic": "market"})

    after = {path.relative_to(output_dir): path.read_bytes() for path in output_dir.rglob("*") if path.is_file()}
    assert after == before
