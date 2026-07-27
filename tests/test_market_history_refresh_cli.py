from __future__ import annotations

import json

from fund_agent import cli


class StubMarketHistoryService:
    def refresh_index_histories(self, *, now):
        return {
            "generated_at": now.isoformat(),
            "indices": [
                {
                    "symbol": "000001",
                    "name": "上证指数",
                    "status": "success",
                    "as_of": "2026-07-01",
                    "updated_at": now.isoformat(),
                    "expires_at": "2026-07-02T00:00:00+00:00",
                    "source": "akshare",
                    "stale": False,
                    "fallback_used": False,
                    "warnings": [],
                }
            ],
            "success_count": 1,
            "fallback_count": 0,
            "unavailable_count": 0,
            "warnings": [],
        }


def test_refresh_market_history_cli_writes_structured_summary(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        cli,
        "_build_cli_market_history_service",
        lambda _args: StubMarketHistoryService(),
    )

    result = cli.main(
        [
            "refresh-market-history",
            "--provider",
            "akshare",
            "--as-of",
            "2026-07-01",
            "--output-dir",
            str(tmp_path),
        ]
    )

    payload_path = tmp_path / "market" / "index_refresh_report.json"
    assert result == 0
    assert payload_path.is_file()
    assert json.loads(payload_path.read_text(encoding="utf-8"))["success_count"] == 1
    assert "Market index refresh report:" in capsys.readouterr().out


def test_refresh_market_history_cli_rejects_fixture_provider(tmp_path, capsys):
    result = cli.main(
        [
            "refresh-market-history",
            "--provider",
            "fixture",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert result == 2
    assert "requires --provider akshare" in capsys.readouterr().out
