import json
from pathlib import Path

from fund_agent.agents import run_research
from fund_agent.models import FundRecord, ProviderHealth, ProviderWarning
from fund_agent.report import render_json, write_json_report


def test_json_report_contains_machine_readable_sections(tmp_path):
    health = ProviderHealth(
        provider="fixture",
        started_at="2026-06-23T00:00:00+00:00",
        finished_at="2026-06-23T00:00:01+00:00",
        duration_ms=1000,
        live_row_count=1,
        mapped_row_count=1,
        warnings=(ProviderWarning(code="skipped_rows", message="sample", severity="info"),),
    )
    result = run_research(
        [FundRecord(code="510300", name="沪深300ETF", category="ETF", nav=5.0)],
        as_of="2026-06-23",
        provider_health=(health,),
    )

    payload = render_json(result)
    path = write_json_report(result, tmp_path)
    loaded = json.loads(path.read_text(encoding="utf-8"))

    assert path == tmp_path / "fund_agent_report.json"
    assert payload["as_of"] == "2026-06-23"
    assert payload["data_quality_grade"] == "normal"
    assert payload["provider_health"][0]["provider"] == "fixture"
    assert payload["provider_warnings"][0]["code"] == "skipped_rows"
    assert payload["candidates"]
    assert payload["valuations"]
    assert "portfolio" in payload
    assert "risk_issues" in payload
    assert "snapshot_delta" in payload
    assert loaded["report_metadata"]["format"] == "fund_agent_report_json"


def test_cli_writes_json_report(tmp_path):
    from fund_agent.cli import main

    exit_code = main(["demo", "--output-dir", str(tmp_path), "--as-of", "2026-06-23"])

    path = tmp_path / "fund_agent_report.json"
    trace_path = tmp_path / "traces" / "provider-2026-06-23.json"
    assert exit_code == 0
    assert path.exists()
    assert trace_path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["as_of"] == "2026-06-23"
