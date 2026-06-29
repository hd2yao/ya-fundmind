import json

from fund_agent.experiment_scoring import (
    ExperimentScoringConfig,
    experiment_score_summary,
    run_experiment_scoring,
)


def _report_payload():
    return {
        "schema_version": "1.0",
        "as_of": "2026-06-23",
        "candidates": [
            {"code": "510300", "name": "沪深300ETF", "score": 8.0},
            {"code": "000001", "name": "缺字段基金", "score": 6.0},
        ],
        "risk_issues": [{"code": "510300", "severity": "Low", "message": "main risk"}],
    }


def _signals_payload():
    return {
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
                "metadata": {"window": "1m"},
            },
            {
                "signal_id": "tiantian:510300:drawdown:1m:max_drawdown",
                "source": "tiantian",
                "code": "510300",
                "category": "drawdown",
                "value": -25.0,
                "direction": "negative",
                "quality_grade": "normal",
                "eligible": True,
                "metadata": {},
            },
            {
                "signal_id": "tiantian:510300:volatility:1m:volatility",
                "source": "tiantian",
                "code": "510300",
                "category": "volatility",
                "value": 35.0,
                "direction": "negative",
                "quality_grade": "normal",
                "eligible": True,
                "metadata": {},
            },
            {
                "signal_id": "tiantian:000001:return:1m:total_return",
                "source": "tiantian",
                "code": "000001",
                "category": "return",
                "value": None,
                "direction": "positive",
                "quality_grade": "normal",
                "eligible": True,
                "metadata": {},
            },
        ],
        "excluded_signals": [],
        "display_only_signals": [
            {
                "signal_id": "tiantian:510300:display_only:fund_manager",
                "source": "tiantian",
                "code": "510300",
                "category": "display_only",
                "value": "张三",
            }
        ],
    }


def test_eligible_return_signal_adjusts_experiment_score_without_overwriting_base_score():
    result = run_experiment_scoring(
        report_payload=_report_payload(),
        signals_payload=_signals_payload(),
        config=ExperimentScoringConfig(max_score_adjustment=1.0),
    )

    score = result["experiment_scores"][0]
    assert score["code"] == "510300"
    assert score["base_score"] == 8.0
    assert score["experiment_score"] != score["base_score"]
    assert score["score_delta"] != 0
    assert result["not_production_model"] is True


def test_bad_quality_unstable_display_and_missing_signals_are_excluded():
    payload = _signals_payload()
    payload["eligible_signals"].extend(
        [
            {
                "signal_id": "bad:degraded",
                "source": "tiantian",
                "code": "510300",
                "category": "return",
                "value": 1.0,
                "quality_grade": "degraded",
                "eligible": True,
            },
            {
                "signal_id": "bad:warning",
                "source": "tiantian",
                "code": "510300",
                "category": "return",
                "value": 1.0,
                "quality_grade": "warning",
                "eligible": True,
            },
            {
                "signal_id": "bad:unstable",
                "source": "tiantian",
                "code": "510300",
                "category": "return",
                "value": 1.0,
                "quality_grade": "normal",
                "eligible": True,
                "metadata": {"annualized_return_unstable": True},
            },
            {
                "signal_id": "bad:stale",
                "source": "tiantian",
                "code": "510300",
                "category": "return",
                "value": 1.0,
                "quality_grade": "normal",
                "eligible": True,
                "metadata": {"stale": True},
            },
        ]
    )

    result = run_experiment_scoring(
        report_payload=_report_payload(),
        signals_payload=payload,
        config=ExperimentScoringConfig(),
    )

    excluded_ids = {
        item["signal_id"]
        for score in result["experiment_scores"]
        for item in score["excluded_signals"]
    }
    assert {"bad:degraded", "bad:warning", "bad:unstable", "bad:stale"}.issubset(excluded_ids)
    assert all("display_only" not in signal_id for signal_id in result["applied_signal_summary"]["by_signal_id"])
    missing_score = next(item for item in result["experiment_scores"] if item["code"] == "000001")
    assert missing_score["experiment_score"] == missing_score["base_score"]


def test_experiment_score_summary_counts_adjusted_and_excluded_signals():
    result = run_experiment_scoring(
        report_payload=_report_payload(),
        signals_payload=_signals_payload(),
        config=ExperimentScoringConfig(),
    )

    summary = experiment_score_summary(result)

    assert summary["total_funds"] == 2
    assert summary["adjusted_count"] == 1
    assert summary["unchanged_count"] == 1
    assert summary["applied_signal_count"] >= 1
    assert summary["excluded_signal_count"] >= 1


def test_provider_level_signal_without_code_does_not_create_blank_score_row():
    signals = {
        "eligible_signals": [
            {
                "signal_id": "fixture:provider:data_quality",
                "source": "fixture",
                "code": "",
                "category": "data_quality",
                "value": "normal",
                "quality_grade": "normal",
                "eligible": True,
            }
        ],
        "excluded_signals": [],
        "display_only_signals": [],
    }

    result = run_experiment_scoring(
        report_payload=_report_payload(),
        signals_payload=signals,
        config=ExperimentScoringConfig(),
    )

    assert {item["code"] for item in result["experiment_scores"]} == {"510300", "000001"}
    assert result["excluded_signal_summary"]["by_signal_id"]["fixture:provider:data_quality"] == 1


def test_zero_applied_signals_include_exclusion_diagnostics():
    signals = {
        "eligible_signals": [
            {
                "signal_id": "bad:warning",
                "source": "tiantian",
                "code": "510300",
                "category": "return",
                "value": 1.0,
                "quality_grade": "warning",
                "eligible": True,
            },
            {
                "signal_id": "bad:stale",
                "source": "cache:tiantian",
                "code": "510300",
                "category": "return",
                "value": 1.0,
                "quality_grade": "normal",
                "eligible": True,
                "metadata": {"stale": True},
            },
        ],
        "excluded_signals": [],
        "display_only_signals": [],
    }

    result = run_experiment_scoring(
        report_payload=_report_payload(),
        signals_payload=signals,
        config=ExperimentScoringConfig(),
    )

    diagnostics = result["exclusion_diagnostics"]
    assert result["applied_signal_summary"]["total"] == 0
    assert diagnostics["excluded_by_reason"]["warning_data_blocked"] == 1
    assert diagnostics["excluded_by_stale_cache"] == 1
    assert diagnostics["primary_reason"] in {"warning_data_blocked", "stale_cache_blocked"}
    assert any("applied signals = 0" in warning["message"] for warning in result["warnings"])
