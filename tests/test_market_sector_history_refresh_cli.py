from __future__ import annotations

import json

from fund_agent import cli
from fund_agent.contract import validate_contract_file
from fund_agent.models import ProviderEndpointTrace, ProviderHealth


class StubMarketSectorHistoryService:
    def __init__(self):
        self.calls = []
        self.last_refresh_health = (
            ProviderHealth(
                provider="akshare",
                provider_version="9.9.9",
                started_at="2026-07-23T00:00:00+00:00",
                finished_at="2026-07-23T00:00:01+00:00",
                duration_ms=1000,
                live_row_count=2,
                mapped_row_count=2,
                cache_write_count=2,
                metadata={
                    "operation": "market_sector_history_refresh",
                    "sector_symbol": "BK1042",
                    "sector_name": "医药商业",
                },
                endpoints=(
                    ProviderEndpointTrace(
                        endpoint="stock_board_industry_index_ths",
                        started_at="2026-07-23T00:00:00+00:00",
                        finished_at="2026-07-23T00:00:01+00:00",
                        duration_ms=1000,
                        attempts=1,
                        success=True,
                        timeout_seconds=20.0,
                        live_row_count=2,
                        mapped_row_count=2,
                    ),
                ),
            ),
        )

    def refresh_sector_histories(self, symbols, *, now, as_of):
        self.calls.append((symbols, now, as_of))
        return {
            "as_of": "2026-07-23",
            "generated_at": now.isoformat(),
            "sectors": [
                {
                    "symbol": "BK1042",
                    "name": "医药商业",
                    "status": "success",
                    "as_of": "2026-07-23",
                    "updated_at": now.isoformat(),
                    "expires_at": "2026-07-24T00:00:00+00:00",
                    "stale": False,
                    "fallback_used": False,
                    "warnings": [],
                }
            ],
            "success_count": 1,
            "fallback_count": 0,
            "unavailable_count": 0,
            "warnings": [],
            "not_production_model": True,
            "main_score_changed": False,
            "main_risk_changed": False,
        }


def test_refresh_market_sector_history_cli_writes_structured_summary(
    monkeypatch,
    tmp_path,
    capsys,
):
    service = StubMarketSectorHistoryService()
    monkeypatch.setattr(
        cli,
        "_build_cli_market_sector_service",
        lambda _args: service,
    )

    result = cli.main(
        [
            "refresh-market-sector-history",
            "--provider",
            "akshare",
            "--symbols",
            "BK1042, BK1036, BK1042",
            "--as-of",
            "2026-07-23",
            "--output-dir",
            str(tmp_path),
        ]
    )

    payload_path = tmp_path / "market" / "sector_history_refresh_report.json"
    assert result == 0
    assert payload_path.is_file()
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["success_count"] == 1
    assert payload["provider_trace"] == "traces/provider-sector-history-2026-07-23.json"
    trace_path = tmp_path / payload["provider_trace"]
    assert trace_path.is_file()
    assert validate_contract_file(trace_path, "trace", strict=True).ok
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace["providers"][0]["sector_symbol"] == "BK1042"
    assert trace["providers"][0]["endpoints"][0]["endpoint"] == "stock_board_industry_index_ths"
    assert service.calls[0][0] == ["BK1042", "BK1036"]
    assert service.calls[0][2] == "2026-07-23"
    assert "Market sector history refresh report:" in capsys.readouterr().out


def test_refresh_market_sector_history_cli_rejects_fixture_provider(tmp_path, capsys):
    result = cli.main(
        [
            "refresh-market-sector-history",
            "--provider",
            "fixture",
            "--symbols",
            "BK1042",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert result == 2
    assert "requires --provider akshare" in capsys.readouterr().out


def test_refresh_market_sector_history_cli_rejects_invalid_symbols(tmp_path, capsys):
    result = cli.main(
        [
            "refresh-market-sector-history",
            "--provider",
            "akshare",
            "--symbols",
            "医药,BK1042",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert result == 2
    assert "comma-separated list of BK codes" in capsys.readouterr().out
