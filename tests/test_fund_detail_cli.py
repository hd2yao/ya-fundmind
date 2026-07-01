import json

from fund_agent.cli import main


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_fund_detail_cli_writes_single_fund_json_and_markdown(tmp_path):
    _write_json(
        tmp_path / "market" / "market_intelligence_report.json",
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
                    "metadata": {"returns": {"1m": 16.5}},
                }
            ],
            "classifications": [
                {"code": "021511", "themes": ["半导体"], "primary_theme": "半导体", "confidence": 0.7}
            ],
            "themes": [{"theme": "半导体", "sample_size": 1}],
        },
    )

    exit_code = main(["fund-detail", "--code", "021511", "--output-dir", str(tmp_path)])

    json_path = tmp_path / "fund_details" / "fund_detail_021511.json"
    md_path = tmp_path / "fund_details" / "fund_detail_021511.md"
    assert exit_code == 0
    assert json_path.exists()
    assert md_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = md_path.read_text(encoding="utf-8")
    assert payload["code"] == "021511"
    assert payload["primary_theme"] == "半导体"
    assert payload["not_production_model"] is True
    assert "宏利半导体产业混合发起C" in markdown
    assert "推荐买入" not in markdown
    assert "建议卖出" not in markdown


def test_fund_detail_cli_multiple_codes_writes_watchlist_summary(tmp_path):
    _write_json(
        tmp_path / "market" / "market_intelligence_report.json",
        {
            "as_of": "2026-06-23",
            "source": "fixture",
            "records": [],
            "classifications": [],
            "themes": [],
        },
    )
    (tmp_path / "runs" / "2026-06-23").mkdir(parents=True)

    exit_code = main(["fund-detail", "--codes", "021511,021580", "--output-dir", str(tmp_path)])

    summary_json = tmp_path / "fund_details" / "watchlist_fund_details.json"
    run_summary_json = tmp_path / "runs" / "2026-06-23" / "fund_details" / "watchlist_fund_details.json"
    assert exit_code == 0
    assert summary_json.exists()
    assert run_summary_json.exists()
    payload = json.loads(summary_json.read_text(encoding="utf-8"))
    assert payload["detail_count"] == 2
    assert [item["code"] for item in payload["fund_details"]] == ["021511", "021580"]
