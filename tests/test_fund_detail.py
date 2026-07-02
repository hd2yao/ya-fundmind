import json

from fund_agent.fund_detail import build_fund_detail_views, render_fund_detail_markdown


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_market_artifacts(output_dir):
    _write_json(
        output_dir / "market" / "market_intelligence_report.json",
        {
            "as_of": "2026-06-23",
            "source": "fixture",
            "records": [
                {
                    "code": "021511",
                    "name": "宏利半导体产业混合发起C",
                    "fund_type": "混合型",
                    "source": "fixture",
                    "as_of": "2026-06-23",
                    "nav": 1.234,
                    "price": None,
                    "scale": 12.3,
                    "valuation_date": "2026-06-23",
                    "exchange_traded": False,
                    "metadata": {"returns": {"1w": 4.2, "1m": 16.5, "3m": 21.0}},
                },
                {
                    "code": "000001",
                    "name": "半导体样本A",
                    "fund_type": "混合型",
                    "source": "fixture",
                    "as_of": "2026-06-23",
                    "scale": 20.0,
                    "metadata": {"returns": {"1m": 10.0}},
                },
            ],
            "classifications": [
                {
                    "code": "021511",
                    "name": "宏利半导体产业混合发起C",
                    "themes": ["半导体"],
                    "primary_theme": "半导体",
                    "confidence": 0.7,
                },
                {
                    "code": "000001",
                    "name": "半导体样本A",
                    "themes": ["半导体"],
                    "primary_theme": "半导体",
                    "confidence": 0.7,
                },
            ],
            "themes": [{"theme": "半导体", "sample_size": 2}],
        },
    )
    _write_json(
        output_dir / "signal_candidates.json",
        {
            "eligible_signals": [
                {
                    "signal_id": "akshare:021511:return:1m",
                    "code": "021511",
                    "category": "return",
                    "evidence": "recent return 1m",
                }
            ],
            "excluded_signals": [],
            "display_only_signals": [],
        },
    )
    _write_json(
        output_dir / "manual_review_queue.json",
        [
            {
                "review_id": "review-1",
                "signal_id": "akshare:021511:return:1m",
                "recommended_status": "needs_data",
                "reason": "needs more evidence",
            }
        ],
    )


def test_build_fund_detail_view_from_existing_market_artifacts(tmp_path):
    _write_market_artifacts(tmp_path)
    watchlist = tmp_path / "watchlist.yaml"
    watchlist.write_text(
        "name: test\nfunds:\n  - code: 021511\n    name: 宏利半导体产业混合发起C\n",
        encoding="utf-8",
    )

    views = build_fund_detail_views(
        codes=["021511"],
        output_dir=tmp_path,
        watchlist_file=watchlist,
    )

    detail = views[0]
    assert detail.code == "021511"
    assert detail.is_watchlist is True
    assert detail.primary_theme == "半导体"
    assert detail.market_rank_context.theme_sample_size == 2
    assert detail.market_rank_context.rank_in_theme_by_1m_return == 1
    assert detail.return_windows["1m"].total_return == 16.5
    assert detail.signal_context.in_signal_candidates is True
    assert detail.signal_context.needs_more_data is True
    assert detail.not_production_model is True


def test_fund_detail_missing_artifacts_degrades_without_failure(tmp_path):
    views = build_fund_detail_views(codes=["021511"], output_dir=tmp_path)

    detail = views[0]
    assert detail.code == "021511"
    assert detail.primary_theme == "unknown"
    assert "missing_market_record" in detail.unknown_reason
    assert "missing_theme_classification" in detail.unknown_reason
    assert detail.data_coverage.status == "missing"
    assert detail.data_coverage.coverage_ratio < 0.5
    assert detail.data_quality_grade in {"warning", "degraded"}
    assert "market_record" in detail.missing_fields
    assert detail.data_quality_warnings
    markdown = render_fund_detail_markdown(detail)
    assert "仅用于观察" in markdown
    assert "推荐买入" not in markdown
    assert "建议卖出" not in markdown


def test_fund_detail_generalizes_to_arbitrary_watchlist_code_with_coverage_and_peer_context(tmp_path):
    _write_json(
        tmp_path / "market" / "market_intelligence_report.json",
        {
            "as_of": "2026-06-24",
            "records": [
                {
                    "code": "123456",
                    "name": "通用机器人主题基金",
                    "fund_type": "ETF",
                    "source": "fixture",
                    "as_of": "2026-06-24",
                    "scale": 33.0,
                    "metadata": {"returns": {"1m": 12.0, "3m": 18.0, "6m": 25.0, "1y": 40.0}},
                },
                {
                    "code": "654321",
                    "name": "机器人同类样本",
                    "fund_type": "ETF",
                    "source": "fixture",
                    "as_of": "2026-06-24",
                    "scale": 20.0,
                    "metadata": {"returns": {"1m": 6.0}},
                },
            ],
            "classifications": [
                {"code": "123456", "themes": ["机器人"], "primary_theme": "机器人", "confidence": 0.8},
                {"code": "654321", "themes": ["机器人"], "primary_theme": "机器人", "confidence": 0.7},
            ],
            "themes": [{"theme": "机器人", "sample_size": 2}],
        },
    )
    watchlist = tmp_path / "watchlist.yaml"
    watchlist.write_text(
        "name: generic\nfunds:\n  - code: 123456\n    name: 通用机器人主题基金\n    type: ETF\n",
        encoding="utf-8",
    )

    detail = build_fund_detail_views(codes=["123456"], output_dir=tmp_path, watchlist_file=watchlist)[0]

    assert detail.code == "123456"
    assert detail.name == "通用机器人主题基金"
    assert detail.primary_theme == "机器人"
    assert detail.unknown_reason == ""
    assert detail.data_coverage.has_market_record is True
    assert detail.data_coverage.has_theme_classification is True
    assert detail.data_coverage.return_window_count >= 4
    assert detail.data_coverage.coverage_ratio >= 0.6
    assert "market_record" in detail.data_coverage.available_fields
    assert detail.peer_comparison.primary_theme == "机器人"
    assert detail.peer_comparison.peer_sample_size == 2
    assert detail.peer_comparison.sample_status == "sufficient"
    assert detail.peer_comparison.rank_by_1m_return == 1


def test_peer_comparison_marks_insufficient_sample_without_failure(tmp_path):
    _write_json(
        tmp_path / "market" / "market_intelligence_report.json",
        {
            "as_of": "2026-06-24",
            "records": [
                {
                    "code": "777777",
                    "name": "孤立主题基金",
                    "fund_type": "混合型",
                    "source": "fixture",
                    "as_of": "2026-06-24",
                    "metadata": {"returns": {"1m": 3.0}},
                }
            ],
            "classifications": [
                {"code": "777777", "themes": ["稀缺主题"], "primary_theme": "稀缺主题", "confidence": 0.6}
            ],
            "themes": [{"theme": "稀缺主题", "sample_size": 1}],
        },
    )

    detail = build_fund_detail_views(codes=["777777"], output_dir=tmp_path)[0]

    assert detail.peer_comparison.peer_sample_size == 1
    assert detail.peer_comparison.sample_status == "insufficient"
    assert "peer_sample_insufficient" in detail.peer_comparison.warnings


def test_unknown_theme_string_outputs_unknown_reason(tmp_path):
    _write_json(
        tmp_path / "market" / "market_intelligence_report.json",
        {
            "as_of": "2026-06-24",
            "records": [
                {
                    "code": "888888",
                    "name": "未知主题基金",
                    "fund_type": "混合型",
                    "source": "fixture",
                    "as_of": "2026-06-24",
                    "metadata": {"returns": {"1m": 1.0}},
                }
            ],
            "classifications": [
                {"code": "888888", "themes": [], "primary_theme": "unknown", "confidence": 0.0}
            ],
            "themes": [],
        },
    )

    detail = build_fund_detail_views(codes=["888888"], output_dir=tmp_path)[0]

    assert detail.primary_theme == "unknown"
    assert "theme_classification_unknown" in detail.unknown_reason
    assert "theme classification unknown" in detail.data_quality_warnings
