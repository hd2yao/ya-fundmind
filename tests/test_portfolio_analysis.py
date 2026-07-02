import json

from fund_agent.cli import main


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_portfolio_analysis_empty_portfolio_writes_report_without_failure(tmp_path):
    portfolio = tmp_path / "empty_portfolio.yaml"
    portfolio.write_text("name: Empty\ncash_available: 0\nholdings:\n", encoding="utf-8")

    exit_code = main(
        [
            "portfolio-analysis",
            "--portfolio-config",
            str(portfolio),
            "--output-dir",
            str(tmp_path),
            "--as-of",
            "2026-06-23",
        ]
    )

    report_path = tmp_path / "portfolio" / "portfolio_report.json"
    summary_path = tmp_path / "portfolio" / "portfolio_report.md"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    markdown = summary_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert payload["status"] == "empty"
    assert payload["holding_count"] == 0
    assert "portfolio_not_configured" in payload["warnings"]
    assert payload["main_score_changed"] is False
    assert payload["main_risk_changed"] is False
    assert "未配置持仓" in markdown
    assert "买入" not in markdown
    assert "卖出" not in markdown


def test_portfolio_analysis_cli_generates_exposure_concentration_and_overlap(tmp_path):
    portfolio = tmp_path / "portfolio.yaml"
    portfolio.write_text(
        """
name: Test Portfolio
cash_available: 500
holdings:
  - code: 510300
    name: 沪深300ETF
    shares: 100
    cost_nav: 3.7
    buy_date: 2026-02-10
    target_weight: 0.35
  - code: 000311
    name: 华夏沪深300ETF联接A
    shares: 200
    cost_nav: 1.2
    buy_date: 2026-02-11
    target_weight: 0.20
  - code: 110022
    name: 易方达消费行业股票
    shares: 50
    cost_nav: 4.3
    buy_date: 2026-01-15
    target_weight: 0.20
""",
        encoding="utf-8",
    )
    _write_json(
        tmp_path / "fund_agent_report.json",
        {
            "as_of": "2026-06-23",
            "portfolio": {
                "total_value": 901.0,
                "total_cost": 825.0,
                "total_unrealized_return_pct": 9.21,
                "positions": [
                    {
                        "code": "510300",
                        "name": "沪深300ETF",
                        "current_value": 405.0,
                        "unrealized_return_pct": 9.46,
                        "weight": 0.4495,
                        "target_drift": 0.0995,
                    },
                    {
                        "code": "000311",
                        "name": "华夏沪深300ETF联接A",
                        "current_value": 284.0,
                        "unrealized_return_pct": 18.33,
                        "weight": 0.3152,
                        "target_drift": 0.1152,
                    },
                    {
                        "code": "110022",
                        "name": "易方达消费行业股票",
                        "current_value": 212.0,
                        "unrealized_return_pct": -1.4,
                        "weight": 0.2353,
                        "target_drift": 0.0353,
                    },
                ],
            },
        },
    )
    _write_json(
        tmp_path / "market" / "market_intelligence_report.json",
        {
            "as_of": "2026-06-23",
            "records": [
                {"code": "510300", "name": "沪深300ETF", "fund_type": "ETF", "source": "fixture"},
                {"code": "000311", "name": "华夏沪深300ETF联接A", "fund_type": "ETF联接", "source": "fixture"},
                {"code": "110022", "name": "易方达消费行业股票", "fund_type": "股票型", "source": "fixture"},
            ],
            "classifications": [
                {"code": "510300", "primary_theme": "宽基", "themes": ["宽基"]},
                {"code": "000311", "primary_theme": "宽基", "themes": ["宽基"]},
                {"code": "110022", "primary_theme": "消费", "themes": ["消费"]},
            ],
        },
    )

    exit_code = main(
        [
            "portfolio-analysis",
            "--portfolio-config",
            str(portfolio),
            "--output-dir",
            str(tmp_path),
            "--as-of",
            "2026-06-23",
        ]
    )

    report_path = tmp_path / "portfolio" / "portfolio_report.json"
    summary_path = tmp_path / "portfolio" / "portfolio_report.md"
    run_report = tmp_path / "runs" / "2026-06-23" / "portfolio_report.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    markdown = summary_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert report_path.exists()
    assert summary_path.exists()
    assert run_report.exists()
    assert payload["status"] == "ok"
    assert payload["holding_count"] == 3
    assert payload["total_value"] == 901.0
    assert payload["cash_available"] == 500.0
    assert payload["theme_exposure"]["宽基"]["holding_count"] == 2
    assert payload["theme_exposure"]["宽基"]["weight"] > 0.7
    assert payload["fund_type_exposure"]["ETF"]["holding_count"] == 1
    assert payload["fund_type_exposure"]["ETF联接"]["holding_count"] == 1
    assert payload["fund_type_exposure"]["主动权益"]["holding_count"] == 1
    assert payload["concentration"]["top_holding_code"] == "510300"
    assert payload["concentration"]["top_holding_weight"] == 0.4495
    assert any(issue["issue_type"] == "theme_overlap" for issue in payload["observation_issues"])
    assert any(issue["issue_type"] == "single_holding_concentration" for issue in payload["observation_issues"])
    assert payload["not_production_model"] is True
    assert payload["main_score_changed"] is False
    assert payload["main_risk_changed"] is False
    assert "Portfolio Analysis" in markdown
    assert "宽基" in markdown
    assert "买入" not in markdown
    assert "卖出" not in markdown
