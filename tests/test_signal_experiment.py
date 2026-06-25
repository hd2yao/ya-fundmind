import json

from fund_agent.cli import main
from fund_agent.signal_experiment import evaluate_tiantian_signals


def _report_payload():
    return {
        "schema_version": "1.0",
        "generated_at": "2026-06-23T00:00:00+00:00",
        "generator": "fund_agent",
        "as_of": "2026-06-23",
        "fund_details": [
            {
                "code": "510300",
                "name": "沪深300ETF",
                "scale": 460.5,
                "rating": "5",
                "fund_manager": "张三",
                "fund_company": "华泰柏瑞基金",
                "inception_date": "2012-05-04",
            }
        ],
        "nav_history_summary": {
            "510300": {
                "windows": {
                    "1m": {
                        "count": 20,
                        "total_return": 1.2,
                        "max_drawdown": -2.1,
                        "volatility": 0.8,
                        "data_quality_grade": "normal",
                        "metadata": {
                            "required_points": 20,
                            "actual_points": 20,
                            "window_mode": "nav_points",
                            "annualized_return_unstable": False,
                        },
                    },
                    "3m": {
                        "count": 5,
                        "data_quality_grade": "degraded",
                        "metadata": {
                            "required_points": 60,
                            "actual_points": 5,
                            "annualized_return_unstable": False,
                        },
                    },
                    "6m": {
                        "count": 120,
                        "data_quality_grade": "normal",
                        "metadata": {
                            "required_points": 120,
                            "actual_points": 120,
                            "annualized_return_unstable": True,
                        },
                    },
                }
            }
        },
    }


def test_signal_experiment_excludes_degraded_and_unstable_windows():
    result = evaluate_tiantian_signals(_report_payload())

    eligible_names = {item["signal"] for item in result["eligible_signals"]}
    excluded = {(item["signal"], item["reason"]) for item in result["excluded_signals"]}

    assert "nav_window.1m.total_return" in eligible_names
    assert ("nav_window.3m", "degraded_window") in excluded
    assert ("nav_window.6m.annualized_return", "annualized_return_unstable") in excluded


def test_signal_experiment_keeps_display_only_fields_out_of_eligible_signals():
    result = evaluate_tiantian_signals(_report_payload())

    eligible_names = {item["signal"] for item in result["eligible_signals"]}
    display_only = {item["field"] for item in result["display_only_fields"]}

    assert "fund_manager" in display_only
    assert "fund_company" in display_only
    assert "inception_date" in display_only
    assert all("fund_manager" not in signal for signal in eligible_names)


def test_experiment_tiantian_signals_cli_writes_output(tmp_path):
    report = tmp_path / "fund_agent_report.json"
    report.write_text(json.dumps(_report_payload()), encoding="utf-8")
    output = tmp_path / "tiantian_signal_experiment.json"

    exit_code = main(
        [
            "experiment-tiantian-signals",
            "--input",
            str(report),
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["eligible_signals"]
    assert payload["excluded_signals"]
    assert payload["required_regression_tests"]
    assert (tmp_path / "signal_candidates.json").exists()
