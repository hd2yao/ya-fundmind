import json

from fund_agent.market_intelligence import build_market_trend_report, write_market_trend_outputs


def _write_snapshot(path, *, as_of, themes, hot, grade="normal", warnings=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "generated_at": f"{as_of}T00:00:00+00:00",
        "as_of": as_of,
        "source": "fixture",
        "provider": "fixture",
        "run_type": "market_scan",
        "total_funds": 100,
        "total_etfs": 10,
        "theme_count": len(themes),
        "hot_theme_count": len(hot),
        "data_quality_grade": grade,
        "theme_rankings": themes,
        "hot_theme_candidates": [item for item in themes if item["theme"] in hot],
        "insufficient_sample_themes": [item for item in themes if item.get("sample_size", 0) < 5],
        "data_quality_summary": {
            "grade": grade,
            "unknown_theme_count": 0,
            "insufficient_sample_theme_count": sum(1 for item in themes if item.get("sample_size", 0) < 5),
        },
        "warnings": warnings or [],
        "not_production_model": True,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_market_trend_report_detects_rank_and_hot_theme_changes(tmp_path):
    snapshots = tmp_path / "market" / "snapshots"
    _write_snapshot(
        snapshots / "2026-06-21.json",
        as_of="2026-06-21",
        themes=[
            {"theme": "人工智能", "sample_size": 12, "avg_return_1m": 4.0, "data_quality_grade": "normal"},
            {"theme": "半导体", "sample_size": 10, "avg_return_1m": 3.0, "data_quality_grade": "normal"},
            {"theme": "消费", "sample_size": 9, "avg_return_1m": 2.0, "data_quality_grade": "normal"},
        ],
        hot=["人工智能", "半导体"],
    )
    _write_snapshot(
        snapshots / "2026-06-22.json",
        as_of="2026-06-22",
        themes=[
            {"theme": "人工智能", "sample_size": 11, "avg_return_1m": 5.0, "data_quality_grade": "normal"},
            {"theme": "半导体", "sample_size": 14, "avg_return_1m": 3.0, "data_quality_grade": "normal"},
            {"theme": "消费", "sample_size": 8, "avg_return_1m": 1.0, "data_quality_grade": "normal"},
        ],
        hot=["人工智能", "半导体"],
    )
    _write_snapshot(
        snapshots / "2026-06-23.json",
        as_of="2026-06-23",
        themes=[
            {"theme": "半导体", "sample_size": 18, "avg_return_1m": 6.0, "data_quality_grade": "normal"},
            {"theme": "芯片", "sample_size": 7, "avg_return_1m": 4.0, "data_quality_grade": "normal"},
            {"theme": "人工智能", "sample_size": 9, "avg_return_1m": 2.0, "data_quality_grade": "normal"},
        ],
        hot=["半导体", "芯片"],
    )

    report = build_market_trend_report(tmp_path / "market", days=30, min_snapshots=3, top_n=10)

    assert report.enough_market_history is True
    assert report.snapshots_processed == 3
    assert report.latest_as_of == "2026-06-23"
    assert report.theme_trends[0]["theme"] == "半导体"
    assert any(item["theme"] == "半导体" for item in report.persistent_hot_themes)
    assert any(item["theme"] == "芯片" for item in report.new_hot_themes)
    assert any(item["theme"] == "人工智能" for item in report.disappeared_hot_themes)
    assert any(item["theme"] == "半导体" for item in report.rising_themes)
    assert any(item["theme"] == "人工智能" for item in report.falling_themes)
    assert report.not_production_model is True


def test_market_trend_one_snapshot_is_insufficient_but_writable(tmp_path):
    snapshots = tmp_path / "market" / "snapshots"
    _write_snapshot(
        snapshots / "2026-06-23.json",
        as_of="2026-06-23",
        themes=[
            {"theme": "半导体", "sample_size": 8, "avg_return_1m": 6.0, "data_quality_grade": "normal"},
        ],
        hot=["半导体"],
        warnings=["sample limited"],
    )

    report = build_market_trend_report(tmp_path / "market", days=30, min_snapshots=3, top_n=5)
    outputs = write_market_trend_outputs(report, tmp_path)

    assert report.enough_market_history is False
    assert report.snapshots_processed == 1
    assert "insufficient_market_history" in " ".join(report.warnings)
    assert outputs.report_path.exists()
    assert outputs.summary_path.exists()
    assert "趋势样本不足" in outputs.summary_path.read_text(encoding="utf-8")
    assert "买入" not in outputs.summary_path.read_text(encoding="utf-8")
    assert "卖出" not in outputs.summary_path.read_text(encoding="utf-8")


def test_market_trend_counts_backfill_snapshots(tmp_path):
    snapshots = tmp_path / "market" / "snapshots"
    _write_snapshot(
        snapshots / "2026-06-22.json",
        as_of="2026-06-22",
        themes=[{"theme": "半导体", "sample_size": 8, "avg_return_1m": 6.0, "data_quality_grade": "normal"}],
        hot=["半导体"],
    )
    _write_snapshot(
        snapshots / "2026-06-23.json",
        as_of="2026-06-23",
        themes=[{"theme": "半导体", "sample_size": 9, "avg_return_1m": 7.0, "data_quality_grade": "normal"}],
        hot=["半导体"],
    )
    for path in snapshots.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["run_type"] = "historical_backfill"
        payload["backfill"] = True
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_market_trend_report(tmp_path / "market", days=30, min_snapshots=2, top_n=5)
    outputs = write_market_trend_outputs(report, tmp_path)
    payload = json.loads(outputs.report_path.read_text(encoding="utf-8"))

    assert report.backfill_snapshot_count == 2
    assert report.run_type_counts["historical_backfill"] == 2
    assert payload["backfill_snapshot_count"] == 2
    assert "backfill_snapshot_count: 2" in outputs.summary_path.read_text(encoding="utf-8")
