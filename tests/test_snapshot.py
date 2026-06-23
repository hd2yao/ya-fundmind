from dataclasses import replace
from pathlib import Path

from fund_agent.agents import run_research
from fund_agent.models import ProviderHealth, ProviderWarning
from fund_agent.providers import FixtureProvider, load_portfolio_file
from fund_agent.snapshot import (
    compare_snapshots,
    load_previous_snapshot,
    snapshot_from_result,
    write_snapshot,
)


def _result(as_of: str):
    funds = FixtureProvider(Path("data/fixtures/funds.json")).fetch_funds()
    holdings = load_portfolio_file(Path("data/portfolio.example.json"))
    return run_research(funds, holdings=holdings, as_of=as_of)


def test_write_snapshot_creates_daily_json(tmp_path):
    result = _result("2026-06-22")

    path = write_snapshot(result, tmp_path)

    assert path == tmp_path / "snapshots" / "2026-06-22.json"
    assert path.exists()
    assert '"as_of": "2026-06-22"' in path.read_text(encoding="utf-8")


def test_load_previous_snapshot_finds_latest_before_as_of(tmp_path):
    write_snapshot(_result("2026-06-20"), tmp_path)
    write_snapshot(_result("2026-06-21"), tmp_path)
    write_snapshot(_result("2026-06-22"), tmp_path)

    previous = load_previous_snapshot(tmp_path, "2026-06-22")

    assert previous is not None
    assert previous["as_of"] == "2026-06-21"


def test_compare_snapshots_reports_score_valuation_and_risk_changes():
    previous = snapshot_from_result(_result("2026-06-21"))
    current_result = _result("2026-06-22")
    first_candidate = current_result.ranked_candidates[0]
    changed_candidate = replace(first_candidate, total_score=first_candidate.total_score + 2.5)
    current_result = replace(
        current_result,
        ranked_candidates=(changed_candidate, *current_result.ranked_candidates[1:]),
    )
    current = snapshot_from_result(current_result)
    current["valuations"]["510300"]["estimated_value"] += 0.1
    current["portfolio"]["risk_issues"].append(
        {"code": "510300", "severity": "High", "message": "新增集中风险"}
    )

    delta = compare_snapshots(previous, current)

    assert delta["score_changes"]
    assert delta["valuation_changes"]
    assert delta["risk_changes"]["added"]
    assert delta["holding_risk_changes"]["risk_count_delta"] == 1


def test_snapshot_includes_provider_health_and_old_snapshots_still_compare():
    health = ProviderHealth(
        provider="akshare",
        started_at="2026-06-23T00:00:00+00:00",
        finished_at="2026-06-23T00:00:01+00:00",
        duration_ms=1000,
        live_row_count=2,
        mapped_row_count=1,
        skipped_row_count=1,
        warnings=(ProviderWarning(code="row_skipped", message="bad row"),),
    )
    result = run_research(
        FixtureProvider(Path("data/fixtures/funds.json")).fetch_funds()[:1],
        as_of="2026-06-23",
        provider_health=(health,),
    )

    snapshot = snapshot_from_result(result)
    old_snapshot = {"as_of": "2026-06-22", "candidates": {}, "valuations": {}}
    delta = compare_snapshots(old_snapshot, snapshot)

    assert snapshot["provider_health"][0]["provider"] == "akshare"
    assert snapshot["provider_health"][0]["warnings"][0]["code"] == "row_skipped"
    assert delta is not None
