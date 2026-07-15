import json
from pathlib import Path
from time import perf_counter

from fund_agent.artifacts import ArtifactCatalog
from fund_agent.research_copilot import ResearchCopilot
from fund_agent.research_evidence import build_evidence_bundle
from fund_agent.research_query import ResearchQueryService


CI_BUDGET_MS = 5000.0


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _build_typical_outputs(root: Path) -> None:
    _write_json(
        root / "market" / "market_intelligence_report.json",
        {
            "schema_version": "1.0",
            "generated_at": "2026-07-13T00:00:00+00:00",
            "generator": "fund_agent",
            "as_of": "2026-07-12",
            "source": "akshare",
            "total_funds": 1000,
            "total_etfs": 200,
            "themes": [{"theme": f"主题-{index}"} for index in range(40)],
            "top_themes": [{"theme": "半导体"}],
            "hot_theme_candidates": [{"theme": "半导体"}],
            "insufficient_sample_themes": [],
            "data_quality_summary": {"grade": "normal"},
            "warnings": [],
            "records": [
                {"record_id": f"record-{index}", "large": "x" * 200}
                for index in range(2000)
            ],
            "classifications": [
                {"record_id": f"record-{index}", "theme": "半导体"}
                for index in range(2000)
            ],
        },
    )
    for index in range(99):
        _write_json(
            root / "snapshots" / f"2026-03-{index + 1:02d}.json",
            {
                "schema_version": "1.0",
                "generated_at": "2026-07-13T00:00:00+00:00",
                "generator": "fund_agent",
                "as_of": f"2026-03-{index + 1:02d}",
                "candidates": {},
                "valuations": {},
                "portfolio": None,
                "provider_health": [],
                "data_quality_grade": "normal",
                "snapshot_delta": {},
            },
        )


def _elapsed_ms(operation):
    started = perf_counter()
    result = operation()
    return result, (perf_counter() - started) * 1000


def test_v2_typical_outputs_stay_within_ci_performance_budget(tmp_path) -> None:
    root = tmp_path / "outputs"
    _build_typical_outputs(root)

    descriptors, catalog_ms = _elapsed_ms(lambda: ArtifactCatalog(root).scan())
    context, query_ms = _elapsed_ms(lambda: ResearchQueryService(root).query("market"))
    bundle, evidence_ms = _elapsed_ms(lambda: build_evidence_bundle(context, root))
    answer, answer_ms = _elapsed_ms(
        lambda: ResearchCopilot(root).answer("今天市场和热门板块有什么变化？")
    )

    assert len(descriptors) == 100
    assert context.status in {"ok", "partial"}
    assert bundle.status in {"ok", "partial"}
    assert answer.answer_status in {"answered", "partial"}
    assert catalog_ms <= CI_BUDGET_MS
    assert query_ms <= CI_BUDGET_MS
    assert evidence_ms <= CI_BUDGET_MS
    assert answer_ms <= CI_BUDGET_MS


def test_market_context_is_compact_and_excludes_full_record_payloads(tmp_path) -> None:
    root = tmp_path / "outputs"
    _build_typical_outputs(root)

    context = ResearchQueryService(root).query("market")
    serialized = json.dumps(context.data, ensure_ascii=False)

    assert "records" not in context.data["market_intelligence"]
    assert "classifications" not in context.data["market_intelligence"]
    assert "record-1999" not in serialized
    assert len(serialized.encode("utf-8")) < 64 * 1024
