from dataclasses import replace
from pathlib import Path

from fund_agent.agents import run_research
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
