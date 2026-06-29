import json

from fund_agent.cli import main


def _write_inputs(tmp_path):
    report = tmp_path / "fund_agent_report.json"
    report.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "as_of": "2026-06-23",
                "candidates": [{"code": "510300", "name": "沪深300ETF", "score": 8.0}],
                "risk_issues": [],
            }
        ),
        encoding="utf-8",
    )
    signals = tmp_path / "signal_candidates.json"
    signals.write_text(
        json.dumps(
            {
                "eligible_signals": [
                    {
                        "signal_id": "tiantian:510300:return:1m:total_return",
                        "source": "tiantian",
                        "code": "510300",
                        "category": "return",
                        "value": 1.2,
                        "direction": "positive",
                        "quality_grade": "normal",
                        "eligible": True,
                    }
                ],
                "excluded_signals": [],
                "display_only_signals": [],
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "experiment_scoring.yaml"
    config.write_text("enable_return_signal: true\nmax_score_adjustment: 1.0\n", encoding="utf-8")
    return report, signals, config


def test_experiment_scoring_cli_writes_report_and_snapshot_summary(tmp_path):
    report, signals, config = _write_inputs(tmp_path)
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    snapshot = snapshot_dir / "2026-06-23.json"
    snapshot.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "generated_at": "2026-06-23T00:00:00+00:00",
                "generator": "fund_agent",
                "as_of": "2026-06-23",
                "candidates": {},
                "valuations": {},
                "portfolio": None,
                "provider_health": [],
                "data_quality_grade": "normal",
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "experiment_scoring_report.json"

    exit_code = main(
        [
            "experiment-scoring",
            "--report",
            str(report),
            "--signals",
            str(signals),
            "--config",
            str(config),
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    snapshot_payload = json.loads(snapshot.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["not_production_model"] is True
    assert payload["experiment_scores"][0]["code"] == "510300"
    assert snapshot_payload["experiment_score_summary"]["total_funds"] == 1


def test_explain_experiment_scoring_cli_writes_markdown(tmp_path):
    source = tmp_path / "experiment_scoring_report.json"
    source.write_text(
        json.dumps(
            {
                "not_production_model": True,
                "experiment_scores": [
                    {
                        "code": "510300",
                        "base_score": 8.0,
                        "experiment_score": 8.3,
                        "score_delta": 0.3,
                        "applied_signals": [{"signal_id": "sig-a"}],
                        "excluded_signals": [],
                    }
                ],
                "experiment_risk_issues": [],
                "applied_signal_summary": {"total": 1},
                "excluded_signal_summary": {"total": 0},
                "warnings": [],
                "disclaimer": "experiment only",
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "experiment_scoring_explained.md"

    exit_code = main(
        [
            "explain-experiment-scoring",
            "--input",
            str(source),
            "--output",
            str(output),
        ]
    )

    markdown = output.read_text(encoding="utf-8")
    assert exit_code == 0
    assert "实验评分总览" in markdown
    assert "不能进入主模型" in markdown


def test_compare_and_sensitivity_cli_write_outputs(tmp_path):
    report, signals, config = _write_inputs(tmp_path)
    experiment = tmp_path / "experiment_scoring_report.json"
    comparison = tmp_path / "experiment_baseline_comparison.json"
    sensitivity = tmp_path / "experiment_config_sensitivity.json"

    assert main(
        [
            "experiment-scoring",
            "--report",
            str(report),
            "--signals",
            str(signals),
            "--config",
            str(config),
            "--output",
            str(experiment),
        ]
    ) == 0
    assert main(
        [
            "compare-experiment-baseline",
            "--report",
            str(report),
            "--experiment",
            str(experiment),
            "--output",
            str(comparison),
        ]
    ) == 0
    assert main(
        [
            "experiment-config-sensitivity",
            "--report",
            str(report),
            "--signals",
            str(signals),
            "--config",
            str(config),
            "--output",
            str(sensitivity),
        ]
    ) == 0

    assert json.loads(comparison.read_text(encoding="utf-8"))["total_funds"] == 1
    assert json.loads(sensitivity.read_text(encoding="utf-8"))["variants"]
