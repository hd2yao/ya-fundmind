import json
from dataclasses import dataclass
from pathlib import Path

from fund_agent.cli import main


@dataclass(frozen=True)
class _FakeContractResult:
    path: Path
    contract_type: str
    ok: bool
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class _FakeContractSummary:
    results: tuple[_FakeContractResult, ...]

    @property
    def ok(self):
        return all(result.ok for result in self.results)


def test_daily_research_cli_generates_run_bundle_and_summaries(tmp_path):
    exit_code = main(
        [
            "daily-research",
            "--provider",
            "fixture",
            "--watchlist-file",
            "configs/watchlist.yaml",
            "--portfolio-config",
            "configs/portfolio.yaml",
            "--output-dir",
            str(tmp_path),
            "--as-of",
            "2026-06-23",
        ]
    )

    run_dir = tmp_path / "runs" / "2026-06-23"
    summary = json.loads((tmp_path / "daily_research_summary.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert run_dir.exists()
    assert (run_dir / "fund_agent_report.json").exists()
    assert (run_dir / "signal_candidates.json").exists()
    assert (run_dir / "manual_review_queue.json").exists()
    assert (run_dir / "daily_research_summary.md").exists()
    assert summary["recommend_main_model"] == "no"
    assert summary["main_score_changed"] is False
    assert summary["main_risk_changed"] is False


def test_daily_research_cli_records_noncritical_step_failure_and_continues(monkeypatch, tmp_path):
    def fail_candidates(*args, **kwargs):
        raise RuntimeError("candidate boom")

    monkeypatch.setattr("fund_agent.cli.generate_signal_candidates_file", fail_candidates)

    exit_code = main(
        [
            "daily-research",
            "--provider",
            "fixture",
            "--watchlist-file",
            "configs/watchlist.yaml",
            "--portfolio-config",
            "configs/portfolio.yaml",
            "--output-dir",
            str(tmp_path),
            "--as-of",
            "2026-06-23",
        ]
    )

    summary = json.loads((tmp_path / "daily_research_summary.json").read_text(encoding="utf-8"))
    failed = [step for step in summary["steps"] if step["status"] == "failed"]
    assert exit_code == 0
    assert failed
    assert failed[0]["step_name"] == "generate_signal_candidates"


def test_daily_research_cli_fails_when_contract_validation_fails(monkeypatch, tmp_path):
    def fail_contract(output_dir):
        return _FakeContractSummary(
            results=(
                _FakeContractResult(
                    path=Path(output_dir) / "fund_agent_report.json",
                    contract_type="report",
                    ok=False,
                    errors=("bad contract",),
                ),
            )
        )

    monkeypatch.setattr("fund_agent.cli.validate_output_dir", fail_contract)

    exit_code = main(
        [
            "daily-research",
            "--provider",
            "fixture",
            "--watchlist-file",
            "configs/watchlist.yaml",
            "--portfolio-config",
            "configs/portfolio.yaml",
            "--output-dir",
            str(tmp_path),
            "--as-of",
            "2026-06-23",
        ]
    )

    summary = json.loads((tmp_path / "daily_research_summary.json").read_text(encoding="utf-8"))
    contract_step = next(step for step in summary["steps"] if step["step_name"] == "validate_contract")
    assert exit_code == 1
    assert summary["status"] == "failed"
    assert contract_step["status"] == "failed"
