import json

from fund_agent.cli import main


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_collect_news_evidence_fixture_deduplicates_and_marks_low_confidence(tmp_path):
    fixture = tmp_path / "news.json"
    _write_json(
        fixture,
        [
            {
                "title": "半导体设备国产化进展提速",
                "source": "fixture-news",
                "published_at": "2026-06-23",
                "url": "https://example.com/news/semiconductor",
                "related_themes": ["半导体"],
                "related_funds": ["510300"],
                "evidence_strength": "medium",
            },
            {
                "title": "半导体设备国产化进展提速",
                "source": "fixture-news",
                "published_at": "2026-06-23",
                "url": "https://example.com/news/semiconductor",
                "related_themes": ["半导体"],
                "related_funds": ["510300"],
                "evidence_strength": "medium",
            },
            {
                "title": "消费主题基金披露月度观点",
                "source": "unknown-blog",
                "published_at": "2026-06-22T09:30:00+08:00",
                "related_themes": ["消费"],
                "related_funds": ["110022"],
                "evidence_strength": "low",
            },
        ],
    )

    exit_code = main(
        [
            "collect-news-evidence",
            "--source",
            "fixture",
            "--fixtures-file",
            str(fixture),
            "--output-dir",
            str(tmp_path),
            "--as-of",
            "2026-06-23",
        ]
    )

    report_path = tmp_path / "news" / "news_evidence_report.json"
    summary_path = tmp_path / "news" / "news_evidence_summary.md"
    run_report = tmp_path / "runs" / "2026-06-23" / "news_evidence_report.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    markdown = summary_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert report_path.exists()
    assert summary_path.exists()
    assert run_report.exists()
    assert payload["as_of"] == "2026-06-23"
    assert payload["evidence_count"] == 2
    assert payload["duplicate_count"] == 1
    assert payload["low_confidence_count"] == 1
    assert payload["by_theme"]["半导体"] == 1
    assert payload["by_fund"]["510300"] == 1
    assert payload["items"][0]["published_at"] == "2026-06-23T00:00:00+00:00"
    assert payload["items"][1]["low_confidence"] is True
    assert "low_confidence" in payload["items"][1]["warnings"]
    assert payload["not_production_model"] is True
    assert payload["main_score_changed"] is False
    assert payload["main_risk_changed"] is False
    assert "News Evidence" in markdown
    assert "low_confidence_count: 1" in markdown
    assert "买入" not in markdown
    assert "卖出" not in markdown
