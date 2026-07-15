import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from fund_agent.cli import main
from fund_agent.contract import validate_contract_file
from fund_agent.mcp_adapter import ResearchMcpAdapter
from fund_agent.research_copilot import ResearchCopilot
from fund_agent.research_evidence import build_evidence_bundle
from fund_agent.research_query import ResearchQueryService
from fund_agent.web_console import build_copilot_view_model, run_copilot_for_web


GENERATED_AT = "2026-07-13T00:00:00+00:00"
AS_OF = "2026-07-12"


def _write_json(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _metadata(payload: dict) -> dict:
    return {
        "schema_version": "1.0",
        "generated_at": GENERATED_AT,
        "generator": "fund_agent",
        "as_of": AS_OF,
        **payload,
    }


def _build_outputs(root: Path) -> list[Path]:
    provider = {
        "provider": "akshare",
        "live_row_count": 100,
        "mapped_row_count": 100,
        "skipped_row_count": 0,
        "cache_write_count": 100,
        "fallback_used": False,
        "warnings": [],
    }
    payloads = {
        root / "fund_agent_report.json": _metadata(
            {
                "data_quality_grade": "normal",
                "provider_health": [provider],
                "provider_warnings": [],
                "candidates": [],
                "valuations": {},
                "portfolio": None,
                "risk_issues": [],
                "snapshot_delta": {},
                "report_metadata": {
                    "not_production_model": True,
                    "main_score_changed": False,
                    "main_risk_changed": False,
                },
            }
        ),
        root / "snapshots" / f"{AS_OF}.json": _metadata(
            {
                "candidates": {},
                "valuations": {},
                "portfolio": None,
                "provider_health": [provider],
                "data_quality_grade": "normal",
                "snapshot_delta": {"warning_count_delta": 0},
            }
        ),
        root / "traces" / f"provider-{AS_OF}.json": _metadata(
            {"providers": [provider]}
        ),
        root / "market" / "market_intelligence_report.json": _metadata(
            {
                "source": "akshare",
                "total_funds": 100,
                "total_etfs": 20,
                "themes": [{"theme": "半导体"}],
                "top_themes": [{"theme": "半导体"}],
                "hot_theme_candidates": [{"theme": "半导体"}],
                "insufficient_sample_themes": [],
                "data_quality_summary": {"grade": "normal"},
                "warnings": [],
            }
        ),
        root / "market" / "market_trend_report.json": _metadata(
            {
                "latest_as_of": AS_OF,
                "source": "akshare",
                "period_days": 20,
                "snapshots_processed": 20,
                "minimum_required_snapshots": 5,
                "enough_market_history": True,
                "persistent_hot_themes": [{"theme": "半导体"}],
                "new_hot_themes": [],
                "disappeared_hot_themes": [],
                "rising_themes": [{"theme": "半导体"}],
                "falling_themes": [],
                "insufficient_history_themes": [],
                "data_quality_trend": [],
                "warnings": [],
            }
        ),
        root / "fund_details" / "fund_detail_510300.json": _metadata(
            {
                "code": "510300",
                "name": "沪深300ETF",
                "fund_type": "ETF",
                "category": "宽基",
                "primary_theme": "大盘宽基",
                "returns": {"1m": 0.01},
                "data_coverage": {"coverage_ratio": 1.0},
                "peer_comparison": {},
                "missing_fields": [],
                "warnings": [],
            }
        ),
        root / "portfolio" / "portfolio_report.json": _metadata(
            {
                "holding_count": 1,
                "total_value": 1000.0,
                "theme_exposure": {"大盘宽基": 1.0},
                "fund_type_exposure": {"ETF": 1.0},
                "concentration": {"top1": 1.0},
                "observation_issues": [],
            }
        ),
        root / "news" / "news_evidence_report.json": _metadata(
            {
                "evidence_count": 1,
                "low_confidence_count": 0,
                "by_source": {"official": 1},
                "by_theme": {"半导体": 1},
                "by_fund": {"510300": 1},
                "items": [{"title": "公开证据", "confidence": "high"}],
            }
        ),
        root / "ops_status.json": _metadata(
            {
                "overall_status": "ok",
                "ops_ready": True,
                "dashboard_ready": True,
                "latest_run": {"as_of": AS_OF},
                "main_model_ready": False,
                "main_model_blockers": ["insufficient_history"],
            }
        ),
        root / "daily_research_summary.json": _metadata(
            {
                "status": "success",
                "data_quality_grade": "normal",
                "provider_warnings": [],
                "missing_artifacts": [],
            }
        ),
        root / "long_horizon_stability.json": _metadata(
            {
                "runs_processed": 20,
                "minimum_required_runs": 20,
                "enough_history": True,
                "blockers": [],
                "main_model_ready": False,
            }
        ),
    }
    return [_write_json(path, payload) for path, payload in payloads.items()]


def _digests(paths: list[Path]) -> dict[str, str]:
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def test_v1_to_query_evidence_copilot_matrix_is_cited_and_read_only(tmp_path) -> None:
    root = tmp_path / "outputs"
    paths = _build_outputs(root)
    before = _digests(paths)
    service = ResearchQueryService(root)

    for topic, code, question in (
        ("market", None, "今天市场和热门板块有什么变化？"),
        ("fund", "510300", "基金 510300 的研究数据如何？"),
        ("portfolio", None, "当前组合的持仓集中度如何？"),
        ("news", None, "有哪些新闻或公告证据？"),
        ("history", None, "和上期相比历史变化如何？"),
        ("quality", None, "本次报告的数据质量如何？"),
    ):
        context = service.query(topic, code=code)
        bundle = build_evidence_bundle(context, root)
        answer = ResearchCopilot(root).answer(question)
        evidence_ids = {item["evidence_id"] for item in answer.evidence}

        assert context.status in {"ok", "partial"}
        assert bundle.findings
        assert answer.answer_status in {"answered", "partial"}
        assert all(finding["evidence_ids"] for finding in answer.findings)
        assert all(
            evidence_id in evidence_ids
            for finding in answer.findings
            for evidence_id in finding["evidence_ids"]
        )

    refused = ResearchCopilot(root).answer("请替我买入 510300 并保证收益")
    assert refused.answer_status == "refused"
    assert refused.findings == ()
    assert refused.evidence == ()
    assert _digests(paths) == before


def test_cli_mcp_and_web_share_the_same_public_copilot_result(tmp_path) -> None:
    root = tmp_path / "outputs"
    paths = _build_outputs(root)
    before = _digests(paths)
    question = "今天市场和热门板块有什么变化？"

    assert main(["research-ask", "--output-dir", str(root), "--question", question]) == 0
    cli_payload = json.loads(
        (root / "copilot" / "research_answer.json").read_text(encoding="utf-8")
    )
    mcp_payload = ResearchMcpAdapter(root).invoke("ask", {"question": question}).data
    web_answer = run_copilot_for_web(question=question, output_dir=root)
    web_view = build_copilot_view_model(asdict(web_answer))

    assert cli_payload["answer_status"] == mcp_payload["answer_status"] == web_view["status"]
    assert cli_payload["summary"] == mcp_payload["summary"] == web_view["summary"]
    assert {
        item["finding_id"] for item in cli_payload["findings"]
    } == {
        item["finding_id"] for item in mcp_payload["findings"]
    } == {
        item["finding_id"] for item in web_view["findings"]
    }
    assert _digests(paths) == before


def test_current_v1_and_v2_contracts_validate_end_to_end(tmp_path) -> None:
    root = tmp_path / "outputs"
    _build_outputs(root)
    assert main(
        ["research-query", "--output-dir", str(root), "--topic", "market"]
    ) == 0
    assert main(["build-research-evidence", "--output-dir", str(root)]) == 0
    assert main(
        [
            "research-ask",
            "--output-dir",
            str(root),
            "--question",
            "今天市场和热门板块有什么变化？",
        ]
    ) == 0
    mcp_path = root / "mcp" / "market_query.json"
    _write_json(
        mcp_path,
        asdict(ResearchMcpAdapter(root).invoke("query", {"topic": "market"})),
    )

    contracts = (
        (root / "fund_agent_report.json", "report"),
        (root / "snapshots" / f"{AS_OF}.json", "snapshot"),
        (root / "traces" / f"provider-{AS_OF}.json", "trace"),
        (root / "research_queries" / "research_context.json", "research_context"),
        (root / "evidence" / "research_evidence.json", "evidence_bundle"),
        (root / "copilot" / "research_answer.json", "research_answer"),
        (mcp_path, "mcp_tool_result"),
    )

    assert all(
        validate_contract_file(path, contract_type, strict=True).ok
        for path, contract_type in contracts
    )
