from fund_agent.signal_review import review_signal_readiness


def _signals_payload():
    return {
        "eligible_signals": [
            {
                "signal_id": "tiantian:510300:return:1m:total_return",
                "source": "tiantian",
                "code": "510300",
                "category": "return",
                "quality_grade": "normal",
                "eligible": True,
                "metadata": {"actual_points": 20, "required_points": 20},
            },
            {
                "signal_id": "tiantian:510300:display_only:fund_manager",
                "source": "tiantian",
                "code": "510300",
                "category": "display_only",
                "quality_grade": "normal",
                "eligible": False,
            },
        ],
        "excluded_signals": [
            {
                "signal_id": "tiantian:510300:return:3m:warning",
                "source": "tiantian",
                "code": "510300",
                "category": "return",
                "quality_grade": "warning",
                "excluded_reason": "warning_data_blocked",
            },
            {
                "signal_id": "tiantian:510300:return:6m:stale",
                "source": "cache:tiantian",
                "code": "510300",
                "category": "return",
                "quality_grade": "normal",
                "excluded_reason": "stale_cache_blocked",
            },
        ],
        "display_only_signals": [],
    }


def _thresholds():
    return [
        {
            "signal_id_pattern": "tiantian:*:return:*",
            "category": "return",
            "source": "tiantian",
            "direction_hypothesis": "positive",
            "min_required_points": 20,
            "required_quality_grade": "normal",
            "exclude_if_stale": True,
            "exclude_if_warning": True,
            "exclude_if_degraded": True,
            "max_score_adjustment_candidate": 0.5,
            "risk_gate_candidate": False,
            "review_status": "proposed",
        },
        {
            "signal_id_pattern": "tiantian:*:display_only:*",
            "category": "display_only",
            "source": "tiantian",
            "direction_hypothesis": "neutral",
            "review_status": "proposed",
        },
    ]


def test_eligible_rate_too_low_needs_data():
    result = review_signal_readiness(
        signals_payload=_signals_payload(),
        stability_payload={"by_signal_id": {}},
        baseline_payload={"exclusion_diagnostics": {"excluded_by_reason": {"stale_cache_blocked": 1}}},
        sensitivity_payload={"sensitivity_summary": {"over_sensitive": False}},
        thresholds=_thresholds(),
    )

    return_item = next(item for item in result["review_items"] if item["category"] == "return")
    assert return_item["recommended_status"] == "needs_data"
    assert return_item["manual_review_required"] is True
    assert result["needs_more_data"]


def test_display_only_and_stale_signals_not_recommended_for_main():
    result = review_signal_readiness(
        signals_payload=_signals_payload(),
        stability_payload={
            "by_signal_id": {
                "tiantian:510300:display_only:fund_manager": {
                    "signal_presence_count": 5,
                    "signal_eligible_count": 0,
                    "signal_eligible_rate": 0.0,
                }
            }
        },
        baseline_payload={"exclusion_diagnostics": {"excluded_by_reason": {"stale_cache_blocked": 1}}},
        sensitivity_payload={"sensitivity_summary": {"over_sensitive": False}},
        thresholds=_thresholds(),
    )

    statuses = {item["category"]: item["recommended_status"] for item in result["review_items"]}
    assert statuses["display_only"] == "rejected"
    assert all(item["recommended_status"] != "approved_for_main_candidate" for item in result["review_items"])


def test_rejected_threshold_status_blocks_signal_even_when_metrics_pass():
    thresholds = [
        {
            "signal_id_pattern": "tiantian:*:return:*:total_return",
            "category": "return",
            "source": "tiantian",
            "direction_hypothesis": "positive",
            "min_required_points": 20,
            "required_quality_grade": "normal",
            "review_status": "rejected",
        }
    ]

    result = review_signal_readiness(
        signals_payload=_signals_payload(),
        stability_payload={
            "by_signal_id": {
                "tiantian:510300:return:1m:total_return": {
                    "signal_presence_count": 10,
                    "signal_eligible_count": 9,
                    "signal_eligible_rate": 0.9,
                }
            }
        },
        baseline_payload={"exclusion_diagnostics": {"excluded_by_reason": {}}},
        sensitivity_payload={"sensitivity_summary": {"over_sensitive": False}},
        thresholds=thresholds,
    )

    item = result["review_items"][0]
    assert item["recommended_status"] == "rejected"
    assert result["rejected_or_blocked"][0]["signal_id"] == "tiantian:*:return:*:total_return"


def test_config_sensitivity_too_high_needs_review():
    result = review_signal_readiness(
        signals_payload={
            "eligible_signals": [
                {
                    "signal_id": "tiantian:510300:return:1m:total_return",
                    "source": "tiantian",
                    "category": "return",
                    "quality_grade": "normal",
                    "eligible": True,
                }
            ],
            "excluded_signals": [],
            "display_only_signals": [],
        },
        stability_payload={
            "by_signal_id": {
                "tiantian:510300:return:1m:total_return": {
                    "signal_presence_count": 10,
                    "signal_eligible_count": 9,
                    "signal_eligible_rate": 0.9,
                }
            }
        },
        baseline_payload={"exclusion_diagnostics": {"excluded_by_reason": {}}},
        sensitivity_payload={"sensitivity_summary": {"over_sensitive": True}},
        thresholds=_thresholds(),
    )

    item = result["review_items"][0]
    assert item["recommended_status"] == "needs_review"
    assert item["config_sensitivity_grade"] == "unstable"
