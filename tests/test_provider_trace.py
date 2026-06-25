import json
import os
from datetime import datetime, timedelta, timezone

from fund_agent.agents import run_research
from fund_agent.cache import FundCache
from fund_agent.models import FundRecord, ProviderEndpointTrace, ProviderHealth, ProviderWarning
from fund_agent.providers import AkshareProvider
from fund_agent.trace import write_provider_trace


class FakeDataFrame:
    def __init__(self, rows):
        self._rows = rows

    def iterrows(self):
        return iter(self._rows)


class TraceAkshare:
    __version__ = "9.9.9"

    def fund_open_fund_rank_em(self, symbol):
        return FakeDataFrame(
            [
                (0, {"基金代码": "000311", "基金简称": "沪深300增强A", "单位净值": "1.25"}),
                (1, {"基金代码": "", "基金简称": ""}),
            ]
        )

    def fund_etf_spot_em(self):
        return FakeDataFrame([])


def test_provider_trace_writes_endpoint_and_health_details(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    provider = AkshareProvider(ak_module=TraceAkshare(), cache=cache)
    funds = provider.fetch_funds(as_of="2026-06-23")
    result = run_research(funds, as_of="2026-06-23", provider_health=(provider.last_health,))

    path = write_provider_trace(result, tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert path == tmp_path / "traces" / "provider-2026-06-23.json"
    assert payload["schema_version"] == "1.0"
    assert payload["generator"] == "fund_agent"
    assert payload["generated_at"]
    assert payload["as_of"] == "2026-06-23"
    assert payload["providers"][0]["provider"] == "akshare"
    assert payload["providers"][0]["endpoints"][0]["endpoint"] == "fund_open_fund_rank_em"
    assert payload["providers"][0]["live_row_count"] == 2
    assert payload["providers"][0]["mapped_row_count"] == 1
    assert payload["providers"][0]["skipped_row_count"] == 1
    assert "token" not in json.dumps(payload).lower()


class FailingAkshare:
    __version__ = "9.9.9"

    def fund_open_fund_rank_em(self, symbol):
        raise RuntimeError("network down")

    def fund_etf_spot_em(self):
        raise RuntimeError("etf down")


def test_provider_trace_is_written_when_live_falls_back_to_cache(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    cache.upsert_funds(
        [FundRecord(code="510300", name="沪深300ETF", category="ETF", nav=5.0, source="akshare")],
        as_of="2026-06-23",
    )
    provider = AkshareProvider(ak_module=FailingAkshare(), cache=cache)
    funds = provider.fetch_funds(as_of="2026-06-23")
    result = run_research(funds, as_of="2026-06-23", provider_health=(provider.last_health,))

    payload = json.loads(write_provider_trace(result, tmp_path).read_text(encoding="utf-8"))

    assert payload["providers"][0]["fallback_used"] is True
    assert payload["providers"][0]["fallback_source"] == "cache"
    assert payload["providers"][0]["warnings"]


def test_provider_trace_retention_prunes_old_trace_files(tmp_path):
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    old_by_age = trace_dir / "provider-2026-05-01.json"
    old_by_count = trace_dir / "provider-2026-06-20.json"
    keep = trace_dir / "provider-2026-06-22.json"
    for path in (old_by_age, old_by_count, keep):
        path.write_text("{}", encoding="utf-8")
    now = datetime(2026, 6, 23, tzinfo=timezone.utc)
    old_by_age.touch()
    old_by_count.touch()
    keep.touch()

    os.utime(old_by_age, (now.timestamp() - timedelta(days=60).total_seconds(),) * 2)
    os.utime(old_by_count, (now.timestamp() - timedelta(days=3).total_seconds(),) * 2)
    os.utime(keep, (now.timestamp() - timedelta(days=1).total_seconds(),) * 2)

    result = run_research(
        [FundRecord(code="510300", name="沪深300ETF", category="ETF", nav=5.0)],
        as_of="2026-06-23",
    )

    path = write_provider_trace(
        result,
        tmp_path,
        retention_days=30,
        max_trace_files=2,
        now=now,
    )

    assert path.exists()
    assert not old_by_age.exists()
    assert not old_by_count.exists()
    assert keep.exists()


def test_tiantian_provider_trace_contract(tmp_path):
    health = ProviderHealth(
        provider="tiantian",
        provider_version=None,
        started_at="2026-06-23T00:00:00+00:00",
        finished_at="2026-06-23T00:00:01+00:00",
        duration_ms=1000,
        live_row_count=2,
        mapped_row_count=2,
        cache_write_count=2,
        cache_read_count=3,
        metadata={
            "windows_requested": ["1m", "3m"],
            "windows_generated": ["1m"],
        },
        endpoints=(
            ProviderEndpointTrace(
                endpoint="tiantian_fund_detail",
                started_at="2026-06-23T00:00:00+00:00",
                finished_at="2026-06-23T00:00:01+00:00",
                duration_ms=1000,
                attempts=2,
                timeout_seconds=20,
                live_row_count=1,
                mapped_row_count=1,
            ),
        ),
    )
    result = run_research(
        [FundRecord(code="510300", name="沪深300ETF", category="ETF", nav=5.0)],
        as_of="2026-06-23",
        provider_health=(health,),
    )

    payload = json.loads(write_provider_trace(result, tmp_path).read_text(encoding="utf-8"))

    assert payload["providers"][0]["provider"] == "tiantian"
    assert payload["providers"][0]["endpoints"][0]["endpoint"] == "tiantian_fund_detail"
    assert payload["providers"][0]["endpoints"][0]["attempts"] == 2
    assert payload["providers"][0]["endpoints"][0]["timeout_seconds"] == 20
    assert payload["providers"][0]["cache_read_count"] == 3
    assert payload["providers"][0]["windows_requested"] == ["1m", "3m"]
    assert payload["providers"][0]["windows_generated"] == ["1m"]
