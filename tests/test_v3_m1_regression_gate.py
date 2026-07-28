from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from fund_agent.contract import validate_output_dir


REPO_ROOT = Path(__file__).resolve().parents[1]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_ops(script_name: str, output_dir: Path, *, as_of: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "YA_FUNDMIND_PROJECT_DIR": str(REPO_ROOT),
            "PYTHON_BIN": sys.executable,
            "OUTPUT_DIR": str(output_dir),
            "AS_OF": as_of,
            "PROVIDER": "fixture",
            "ENABLE_MARKET_INTELLIGENCE": "false",
            "REFRESH_DASHBOARD": "true",
            "DAYS": "7",
            "WEEKLY_DAYS": "7",
        }
    )
    return subprocess.run(
        ["bash", str(REPO_ROOT / "scripts" / script_name)],
        cwd=REPO_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_success(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def test_v3_m1_fixture_ops_keep_research_outputs_and_main_models_unchanged(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    as_of = date.today().isoformat()
    watched_config = REPO_ROOT / "configs" / "watchlist.yaml"
    portfolio_config = REPO_ROOT / "configs" / "portfolio.yaml"
    config_digests = {path: _digest(path) for path in (watched_config, portfolio_config)}

    _assert_success(_run_ops("run_daily_ops.sh", output_dir, as_of=as_of))
    _assert_success(_run_ops("run_weekly_ops.sh", output_dir, as_of=as_of))

    daily = _read_json(output_dir / "daily_research_summary.json")
    run_metadata = _read_json(output_dir / "runs" / as_of / "run_metadata.json")
    weekly = _read_json(output_dir / "weekly_research_summary.json")
    news = _read_json(output_dir / "news" / "news_evidence_report.json")
    portfolio = _read_json(output_dir / "portfolio" / "portfolio_report.json")
    ops_status = _read_json(output_dir / "ops_status.json")
    report = _read_json(output_dir / "fund_agent_report.json")

    assert daily["status"] == "success"
    assert daily["missing_artifacts"] == []
    assert daily["main_score_changed"] is False
    assert daily["main_risk_changed"] is False
    assert daily["not_production_model"] is True
    assert run_metadata["status"] == "success"
    assert news["evidence_count"] > 0
    assert news["main_score_changed"] is False
    assert news["main_risk_changed"] is False
    assert news["not_production_model"] is True
    assert portfolio["main_score_changed"] is False
    assert portfolio["main_risk_changed"] is False
    assert portfolio["not_production_model"] is True
    assert weekly["runs_processed"] == 1
    assert weekly["not_production_model"] is True
    assert weekly["no_trading_simulation"] is True
    assert ops_status["main_score_changed"] is False
    assert ops_status["main_risk_changed"] is False
    assert ops_status["latest_run_status"] == "success"
    assert ops_status["dashboard_ready"] is True
    assert "不构成投资建议" in report["report_metadata"]["disclaimer"]
    assert (output_dir / "dashboard" / "index.html").exists()
    assert (output_dir / "dashboard" / "news.html").exists()

    contracts = validate_output_dir(output_dir)
    assert contracts.ok, [f"{item.contract_type}: {item.errors}" for item in contracts.results]
    assert {path: _digest(path) for path in config_digests} == config_digests
