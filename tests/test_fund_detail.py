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
    assert detail.data_quality_grade in {"warning", "degraded"}
    assert "market_record" in detail.missing_fields
    assert detail.data_quality_warnings
    markdown = render_fund_detail_markdown(detail)
    assert "仅用于观察" in markdown
    assert "推荐买入" not in markdown
    assert "建议卖出" not in markdown
