import json

from fund_agent.models import SignalCandidate
from fund_agent.signal_candidates import generate_signal_candidates


def _report_payload():
    return {
        "schema_version": "1.0",
        "as_of": "2026-06-23",
        "data_quality_grade": "normal",
        "provider_health": [
            {
                "provider": "akshare",
                "fallback_used": False,
                "warnings": [],
            }
        ],
        "fund_details": [
            {
                "code": "510300",
                "name": "沪深300ETF",
                "scale": 460.5,
                "rating": "5",
                "fund_manager": "张三",
                "fund_company": "华泰柏瑞基金",
                "inception_date": "2012-05-04",
                "source": "tiantian",
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
                        "count": 3,
                        "data_quality_grade": "degraded",
                        "metadata": {"required_points": 60, "actual_points": 3},
                    },
                    "6m": {
                        "count": 120,
                        "annualized_return": 20.0,
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
        "candidates": [
            {"code": "510300", "name": "沪深300ETF", "category": "ETF"},
            {"code": "000001", "name": "缺字段基金", "category": "混合"},
        ],
        "valuations": {
            "510300": {"code": "510300", "confidence": "High"},
            "000001": {"code": "000001", "confidence": None},
        },
    }


def test_signal_candidate_dataclass_is_independent_from_scoring_models():
    candidate = SignalCandidate(
        signal_id="tiantian:510300:return:1m",
        source="tiantian",
        code="510300",
        category="return",
        value=1.2,
        direction="positive",
        quality_grade="normal",
        eligible=True,
        excluded_reason=None,
        evidence="1m total_return",
    )

    assert candidate.signal_id == "tiantian:510300:return:1m"
    assert candidate.metadata == {}


def test_tiantian_normal_window_generates_eligible_candidates():
    result = generate_signal_candidates(_report_payload())

    eligible_ids = {item["signal_id"] for item in result["eligible_signals"]}

    assert "tiantian:510300:return:1m:total_return" in eligible_ids
    assert "tiantian:510300:drawdown:1m:max_drawdown" in eligible_ids
    assert "tiantian:510300:volatility:1m:volatility" in eligible_ids


def test_degraded_and_unstable_windows_are_excluded():
    result = generate_signal_candidates(_report_payload())

    excluded = {(item["signal_id"], item["excluded_reason"]) for item in result["excluded_signals"]}

    assert ("tiantian:510300:data_quality:3m", "degraded_window") in excluded
    assert ("tiantian:510300:return:6m:annualized_return", "annualized_return_unstable") in excluded


def test_display_only_fields_do_not_enter_eligible_signals():
    result = generate_signal_candidates(_report_payload())

    eligible_ids = {item["signal_id"] for item in result["eligible_signals"]}
    display_ids = {item["signal_id"] for item in result["display_only_signals"]}

    assert "tiantian:510300:display_only:fund_manager" in display_ids
    assert "tiantian:510300:display_only:fund_company" in display_ids
    assert all("fund_manager" not in signal_id for signal_id in eligible_ids)


def test_akshare_missing_fields_are_not_fabricated():
    result = generate_signal_candidates(_report_payload())

    all_ids = {
        item["signal_id"]
        for section in ("eligible_signals", "excluded_signals", "display_only_signals")
        for item in result[section]
    }

    assert "akshare:000001:liquidity:scale_billion" not in all_ids
    assert "akshare:510300:valuation:confidence" in all_ids


def test_generate_signal_candidates_summary_counts():
    result = generate_signal_candidates(_report_payload())

    assert result["summary"]["total_signals"] == (
        result["summary"]["eligible_count"]
        + result["summary"]["excluded_count"]
        + result["summary"]["display_only_count"]
    )
    assert result["required_regression_tests"]
