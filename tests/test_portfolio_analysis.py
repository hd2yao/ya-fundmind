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


def test_portfolio_analysis_keeps_missing_valuations_unknown_instead_of_zero(tmp_path):
    portfolio = tmp_path / "portfolio.yaml"
    portfolio.write_text(
        """
name: Missing valuation
cash_available: 0
holdings:
  - code: 510300
    name: 沪深300ETF
    shares: 100
    cost_nav: 3.7
    target_weight: 0.5
""",
        encoding="utf-8",
    )
    _write_json(tmp_path / "fund_agent_report.json", {"as_of": "2026-06-23", "portfolio": {"positions": []}})
    _write_json(
        tmp_path / "market" / "market_intelligence_report.json",
        {"records": [{"code": "510300", "fund_type": "ETF"}]},
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

    payload = json.loads((tmp_path / "portfolio" / "portfolio_report.json").read_text(encoding="utf-8"))
    position = payload["positions"][0]

    assert exit_code == 0
    assert payload["valuation_status"] == "unavailable"
    assert payload["total_value"] is None
    assert payload["total_unrealized_return_pct"] is None
    assert position["current_value"] is None
    assert position["weight"] is None
    assert position["target_drift"] is None
    assert payload["theme_exposure"]["unknown"]["weight"] is None
    assert payload["concentration"]["top_holding_weight"] is None
    assert any(issue["issue_type"] == "missing_position_valuation" for issue in payload["observation_issues"])


def test_portfolio_analysis_marks_mixed_valuations_partial_without_partial_total(tmp_path):
    portfolio = tmp_path / "portfolio.yaml"
    portfolio.write_text(
        """
name: Partial valuation
cash_available: 0
holdings:
  - code: 510300
    name: 沪深300ETF
    shares: 100
    cost_nav: 3.7
  - code: 000311
    name: 沪深300ETF联接
    shares: 100
    cost_nav: 1.2
""",
        encoding="utf-8",
    )
    _write_json(
        tmp_path / "fund_agent_report.json",
        {
            "as_of": "2026-06-23",
            "portfolio": {"positions": [{"code": "510300", "current_value": 405.0}]},
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

    payload = json.loads((tmp_path / "portfolio" / "portfolio_report.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["valuation_status"] == "partial"
    assert payload["valued_position_count"] == 1
    assert payload["unvalued_position_count"] == 1
    assert payload["valued_total_value"] == 405.0
    assert payload["total_value"] is None
    assert payload["total_unrealized_return_pct"] is None
    assert all(position["weight"] is None for position in payload["positions"])


def test_portfolio_analysis_does_not_derive_weights_from_a_zero_total(tmp_path):
    portfolio = tmp_path / "portfolio.yaml"
    portfolio.write_text(
        """
name: Explicit zero valuation
cash_available: 0
holdings:
  - code: 510300
    name: 沪深300ETF
    shares: 100
    cost_nav: 3.7
""",
        encoding="utf-8",
    )
    _write_json(
        tmp_path / "fund_agent_report.json",
        {
            "as_of": "2026-06-23",
            "portfolio": {"positions": [{"code": "510300", "current_value": 0.0}]},
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

    payload = json.loads((tmp_path / "portfolio" / "portfolio_report.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["valuation_status"] == "complete"
    assert payload["total_value"] == 0.0
    assert payload["positions"][0]["weight"] is None
    assert payload["concentration"] == {"top_holding_code": None, "top_holding_weight": None, "hhi": None}
