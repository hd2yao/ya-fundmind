from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

from fund_agent import cli
from fund_agent.cache import FundCache
from fund_agent.contract import validate_contract_file
from fund_agent.models import (
    FundCatalogEntry,
    FundFee,
    FundProfile,
    FundTradingRule,
    ProviderEndpointTrace,
    ProviderHealth,
)


class FakeFundProfileProvider:
    provider_version = "test"

    def __init__(self):
        self.calls: list[str] = []
        self.last_health = None

    def _record(self, operation: str, endpoint: str, *, rows: int = 1) -> None:
        self.calls.append(operation)
        timestamp = "2026-07-28T00:00:00+00:00"
        self.last_health = ProviderHealth(
            provider="akshare",
            provider_version=self.provider_version,
            started_at=timestamp,
            finished_at=timestamp,
            duration_ms=1,
            live_row_count=rows,
            mapped_row_count=rows,
            endpoints=(
                ProviderEndpointTrace(
                    endpoint=endpoint,
                    started_at=timestamp,
                    finished_at=timestamp,
                    duration_ms=1,
                    live_row_count=rows,
                    mapped_row_count=rows,
                ),
            ),
            metadata={"operation": operation},
        )

    def fetch_fund_catalog(self, *, as_of):
        self._record("catalog", "fund_name_em")
        return [
            FundCatalogEntry(
                code="021511",
                name="示例混合A",
                fund_type="混合型",
                catalog_sources=("fund_name_em",),
                source="akshare",
                as_of=as_of,
            )
        ]

    def fetch_purchase_statuses(self, *, as_of):
        self._record("purchase", "fund_purchase_em")
        return [
            FundTradingRule(
                code="021511",
                purchase_status="开放申购",
                redemption_status="开放赎回",
                source="akshare",
                as_of=as_of,
            )
        ]

    def fetch_fund_profile(self, code, *, as_of):
        self._record("profile", "fund_overview_em")
        return FundProfile(
            code=code,
            name="示例混合A",
            fund_type="混合型",
            fund_company="示例基金",
            source="akshare",
            as_of=as_of,
        )

    def fetch_fund_trading_rule(self, code, *, as_of):
        self._record("rule", "fund_fee_em")
        return FundTradingRule(
            code=code,
            purchase_status="开放申购",
            redemption_status="开放赎回",
            source="akshare",
            as_of=as_of,
        )

    def fetch_fund_fees(self, code, *, as_of):
        self._record("fees", "fund_fee_em")
        return [
            FundFee(
                code=code,
                fee_type="申购费率（前端）",
                condition="小于100万元",
                original_rate="1.20%",
                discounted_rate="0.12%",
                source="akshare",
                as_of=as_of,
            )
        ]


def _runtime(monkeypatch, provider, cache_file):
    config = SimpleNamespace(
        trace_retention_days=30,
        max_trace_files=100,
    )
    monkeypatch.setattr(
        cli,
        "_build_fund_profile_runtime",
        lambda _args: (FundCache(cache_file), provider, config),
    )


def _legacy_row_counts(cache_file) -> tuple[int, int]:
    with sqlite3.connect(cache_file) as connection:
        basics = connection.execute("SELECT COUNT(*) FROM fund_basics").fetchone()[0]
        details = connection.execute("SELECT COUNT(*) FROM fund_details").fetchone()[0]
    return basics, details


def test_reference_refresh_is_explicit_atomic_and_legacy_isolated(
    monkeypatch,
    tmp_path,
):
    cache_file = tmp_path / "funds.sqlite"
    provider = FakeFundProfileProvider()
    _runtime(monkeypatch, provider, cache_file)

    exit_code = cli.main(
        [
            "refresh-fund-profile-reference",
            "--as-of",
            "2026-07-28",
            "--cache-file",
            str(cache_file),
            "--output-dir",
            str(tmp_path),
            "--minimum-entry-count",
            "1",
            "--catalog-minimum-mapped-ratio",
            "0",
            "--purchase-minimum-mapped-ratio",
            "0",
        ]
    )

    cache = FundCache(cache_file)
    report_path = tmp_path / "fund_profiles" / "reference_refresh_report.json"
    trace_path = tmp_path / "traces" / "provider-fund-profile-reference-2026-07-28.json"
    assert exit_code == 0
    assert provider.calls == ["catalog", "purchase"]
    assert [item.code for item in cache.load_catalog_entries()] == ["021511"]
    assert [item.code for item in cache.load_purchase_statuses()] == ["021511"]
    assert _legacy_row_counts(cache_file) == (0, 0)
    assert json.loads(report_path.read_text(encoding="utf-8"))["status"] == "success"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert [endpoint["endpoint"] for item in trace["providers"] for endpoint in item["endpoints"]] == [
        "fund_name_em",
        "fund_purchase_em",
    ]
    assert all("cache_read_count" in endpoint for item in trace["providers"] for endpoint in item["endpoints"])
    assert all("cache_write_count" in endpoint for item in trace["providers"] for endpoint in item["endpoints"])


def test_fetch_fund_profile_writes_valid_artifact_trace_and_only_new_tables(
    monkeypatch,
    tmp_path,
):
    cache_file = tmp_path / "funds.sqlite"
    provider = FakeFundProfileProvider()
    _runtime(monkeypatch, provider, cache_file)

    exit_code = cli.main(
        [
            "fetch-fund-profile",
            "--code",
            "021511",
            "--as-of",
            "2026-07-28",
            "--cache-file",
            str(cache_file),
            "--output-dir",
            str(tmp_path),
        ]
    )

    artifact = tmp_path / "fund_profiles" / "fund_profile-021511.json"
    trace_path = tmp_path / "traces" / "provider-fund-profile-021511-2026-07-28.json"
    assert exit_code == 0
    assert provider.calls == ["profile", "rule", "fees"]
    assert "catalog" not in provider.calls
    assert "purchase" not in provider.calls
    assert validate_contract_file(artifact, "fund_profile", strict=True).ok is True
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["not_production_model"] is True
    assert payload["main_score_changed"] is False
    assert payload["main_risk_changed"] is False
    assert _legacy_row_counts(cache_file) == (0, 0)
    assert trace_path.is_file()


def test_reference_refresh_rejects_incomplete_snapshot_and_keeps_active_data(
    monkeypatch,
    tmp_path,
):
    cache_file = tmp_path / "funds.sqlite"
    cache = FundCache(cache_file)
    cache.replace_fund_catalog_snapshot(
        [FundCatalogEntry(code="000001", name="旧目录", source="akshare")],
        snapshot_id="catalog-old",
        as_of="2026-07-27",
    )
    cache.replace_purchase_snapshot(
        [FundTradingRule(code="000001", purchase_status="暂停申购", source="akshare")],
        snapshot_id="purchase-old",
        as_of="2026-07-27",
    )
    provider = FakeFundProfileProvider()
    _runtime(monkeypatch, provider, cache_file)

    exit_code = cli.main(
        [
            "refresh-fund-profile-reference",
            "--as-of",
            "2026-07-28",
            "--cache-file",
            str(cache_file),
            "--output-dir",
            str(tmp_path),
            "--minimum-entry-count",
            "2",
        ]
    )

    current = FundCache(cache_file)
    assert exit_code == 2
    assert [item.code for item in current.load_catalog_entries()] == ["000001"]
    assert [item.code for item in current.load_purchase_statuses()] == ["000001"]


def test_validate_contract_cli_accepts_fund_profile_artifact(monkeypatch, tmp_path):
    cache_file = tmp_path / "funds.sqlite"
    provider = FakeFundProfileProvider()
    _runtime(monkeypatch, provider, cache_file)
    assert cli.main(
        [
            "fetch-fund-profile",
            "--code",
            "021511",
            "--as-of",
            "2026-07-28",
            "--cache-file",
            str(cache_file),
            "--output-dir",
            str(tmp_path),
        ]
    ) == 0

    artifact = tmp_path / "fund_profiles" / "fund_profile-021511.json"

    assert cli.main(["validate-contract", "--fund-profile", str(artifact)]) == 0


def test_fetch_fund_profile_rejects_invalid_code_before_runtime_build(
    monkeypatch,
    tmp_path,
    capsys,
):
    monkeypatch.setattr(
        cli,
        "_build_fund_profile_runtime",
        lambda _args: (_ for _ in ()).throw(AssertionError("runtime must not be built")),
    )

    exit_code = cli.main(
        [
            "fetch-fund-profile",
            "--code",
            "bad",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 2
    assert "six-digit" in capsys.readouterr().out
