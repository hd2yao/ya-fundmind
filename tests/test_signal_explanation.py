import json

from fund_agent.cli import main
from fund_agent.signal_explanation import explain_signal_candidates


def _candidate_payload():
    return {
        "eligible_signals": [
            {
                "signal_id": "tiantian:510300:return:1m:total_return",
                "source": "tiantian",
                "code": "510300",
                "category": "return",
                "value": 1.2,
                "evidence": "1m total_return",
            }
        ],
        "excluded_signals": [
            {
                "signal_id": "tiantian:510300:data_quality:3m",
                "source": "tiantian",
                "code": "510300",
                "category": "data_quality",
                "excluded_reason": "degraded_window",
                "evidence": "3m degraded",
            }
        ],
        "display_only_signals": [
            {
                "signal_id": "tiantian:510300:display_only:fund_manager",
                "source": "tiantian",
                "code": "510300",
                "category": "display_only",
                "value": "张三",
            }
        ],
        "summary": {
            "total_signals": 3,
            "eligible_count": 1,
            "excluded_count": 1,
            "display_only_count": 1,
            "top_exclusion_reasons": {"degraded_window": 1},
        },
    }


def test_explain_signal_candidates_generates_markdown_and_json_payload():
    result = explain_signal_candidates(_candidate_payload())

    assert "候选信号解释报告" in result["markdown"]
    assert "当前不改变主评分/主风险" in result["markdown"]
    assert "degraded_window" in result["markdown"]
    assert result["json"]["summary"]["eligible_count"] == 1
    assert result["json"]["integration_gaps"]


def test_explain_signal_candidates_cli_writes_markdown_and_json(tmp_path):
    source = tmp_path / "signal_candidates.json"
    source.write_text(json.dumps(_candidate_payload()), encoding="utf-8")
    markdown_output = tmp_path / "signal_candidates_explained.md"
    json_output = tmp_path / "signal_candidates_explained.json"

    exit_code = main(
        [
            "explain-signal-candidates",
            "--input",
            str(source),
            "--output",
            str(markdown_output),
            "--json-output",
            str(json_output),
        ]
    )

    assert exit_code == 0
    assert "当前不改变主评分/主风险" in markdown_output.read_text(encoding="utf-8")
    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["summary"]["total_signals"] == 3
