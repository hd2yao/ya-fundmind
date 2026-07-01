import json

from fund_agent.cli import main


def test_watchlist_detail_cli_reads_watchlist_and_writes_summary(tmp_path):
    watchlist = tmp_path / "watchlist.yaml"
    original = (
        "name: test watchlist\n"
        "funds:\n"
        "  - code: 021511\n"
        "    name: 宏利半导体产业混合发起C\n"
        "    type: 混合型\n"
        "  - code: 021580\n"
        "    name: 华夏人工智能ETF联接D\n"
        "    type: ETF联接\n"
        "  - code: 011452\n"
        "    name: 华泰柏瑞质量成长混合C\n"
        "    type: 混合型\n"
    )
    watchlist.write_text(original, encoding="utf-8")

    exit_code = main(
        [
            "watchlist-detail",
            "--watchlist-file",
            str(watchlist),
            "--output-dir",
            str(tmp_path),
        ]
    )

    json_path = tmp_path / "fund_details" / "watchlist_fund_details.json"
    md_path = tmp_path / "fund_details" / "watchlist_fund_details.md"
    single_json = tmp_path / "fund_details" / "fund_detail_021580.json"
    single_md = tmp_path / "fund_details" / "fund_detail_021580.md"
    assert exit_code == 0
    assert json_path.exists()
    assert md_path.exists()
    assert single_json.exists()
    assert single_md.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["detail_count"] == 3
    assert payload["fund_details"][2]["name"] == "华泰柏瑞质量成长混合C"
    assert payload["fund_details"][1]["fund_type"] == "ETF联接"
    assert payload["fund_details"][1]["latest_detail_json_path"].endswith("fund_detail_021580.json")
    assert payload["not_production_model"] is True
    assert watchlist.read_text(encoding="utf-8") == original
    markdown = md_path.read_text(encoding="utf-8")
    assert "021511" in markdown
    assert "推荐买入" not in markdown
    assert "建议卖出" not in markdown
