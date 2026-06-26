from fund_agent.experiment_scoring import ExperimentScoringConfig, run_experiment_scoring


def test_experiment_risk_issues_are_separate_from_main_risk_issues():
    report = {
        "as_of": "2026-06-23",
        "candidates": [{"code": "510300", "name": "沪深300ETF", "score": 8.0}],
        "risk_issues": [{"code": "510300", "severity": "Low", "message": "main risk"}],
    }
    signals = {
        "eligible_signals": [
            {
                "signal_id": "tiantian:510300:drawdown:1m:max_drawdown",
                "source": "tiantian",
                "code": "510300",
                "category": "drawdown",
                "value": -30.0,
                "direction": "negative",
                "quality_grade": "normal",
                "eligible": True,
            },
            {
                "signal_id": "tiantian:510300:volatility:1m:volatility",
                "source": "tiantian",
                "code": "510300",
                "category": "volatility",
                "value": 40.0,
                "direction": "negative",
                "quality_grade": "normal",
                "eligible": True,
            },
        ],
        "excluded_signals": [
            {
                "signal_id": "tiantian:510300:data_quality:3m",
                "source": "tiantian",
                "code": "510300",
                "category": "data_quality",
                "quality_grade": "degraded",
                "excluded_reason": "degraded_window",
            }
        ],
        "display_only_signals": [],
    }

    result = run_experiment_scoring(
        report_payload=report,
        signals_payload=signals,
        config=ExperimentScoringConfig(),
    )

    issue_types = {issue["issue_type"] for issue in result["experiment_risk_issues"]}
    assert "high_drawdown_candidate" in issue_types
    assert "high_volatility_candidate" in issue_types
    assert "degraded_data_blocked" in issue_types
    assert result["report_main_risk_issues_count"] == 1
    assert "risk_issues" not in result
