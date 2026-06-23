from fund_agent.cache import FundCache
from fund_agent.cli import main
from fund_agent.models import FundRecord, ProviderHealth, ProviderWarning
from fund_agent.providers import AkshareProvider


class FakeDataFrame:
    def __init__(self, rows):
        self._rows = rows

    def iterrows(self):
        return iter(self._rows)


class FailingAkshare:
    __version__ = "9.9.9"

    def fund_open_fund_rank_em(self, symbol):
        raise RuntimeError("network down")

    def fund_etf_spot_em(self):
        raise RuntimeError("etf down")


def test_provider_warning_defaults_to_warning_for_old_callers():
    warning = ProviderWarning(code="legacy", message="old shape")

    assert warning.severity == "warning"


def test_fallback_to_stale_cache_records_warning_and_stale_cache_severity(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    cache.upsert_funds(
        [
            FundRecord(
                code="510300",
                name="沪深300ETF",
                category="ETF",
                nav=5.0,
                source="akshare",
            )
        ],
        as_of="2026-06-23",
        ttl_days=-1,
    )
    provider = AkshareProvider(ak_module=FailingAkshare(), cache=cache)

    funds = provider.fetch_funds(as_of="2026-06-23")

    health = provider.last_health
    assert funds[0].metadata["stale"] is True
    assert health is not None
    assert any(
        warning.code == "live_fallback" and warning.severity == "warning"
        for warning in health.warnings
    )
    assert any(
        warning.code == "stale_cache" and warning.severity == "critical"
        for warning in health.warnings
    )


class PrintingAkshare:
    __version__ = "9.9.9"

    def fund_open_fund_rank_em(self, symbol):
        return FakeDataFrame([])

    def fund_etf_spot_em(self):
        print("progress should be hidden")
        return FakeDataFrame(
            [
                (
                    0,
                    {
                        "代码": "510300",
                        "名称": "沪深300ETF",
                        "最新价": "5.08",
                        "IOPV实时估值": "5.07",
                    },
                )
            ]
        )


def test_akshare_provider_suppresses_vendor_progress_by_default(capsys):
    provider = AkshareProvider(ak_module=PrintingAkshare())

    funds = provider.fetch_funds(as_of="2026-06-23")

    captured = capsys.readouterr()
    assert funds
    assert "progress should be hidden" not in captured.out


def test_akshare_provider_verbose_keeps_vendor_output(capsys):
    provider = AkshareProvider(ak_module=PrintingAkshare(), verbose=True)

    provider.fetch_funds(as_of="2026-06-23")

    captured = capsys.readouterr()
    assert "progress should be hidden" in captured.out


def test_provider_health_detects_critical_warnings():
    health = ProviderHealth(
        provider="akshare",
        started_at="2026-06-23T00:00:00+00:00",
        finished_at="2026-06-23T00:00:01+00:00",
        duration_ms=1000,
        warnings=(ProviderWarning(code="stale_cache", message="expired", severity="critical"),),
    )

    assert health.has_critical_warnings is True


def test_all_watchlist_missing_records_critical_warning(tmp_path):
    watchlist = tmp_path / "watchlist.yaml"
    watchlist.write_text(
        """
funds:
  - code: 999999
""",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "daily",
            "--provider",
            "fixture",
            "--watchlist-file",
            str(watchlist),
            "--output-dir",
            str(tmp_path),
            "--as-of",
            "2026-06-23",
        ]
    )

    markdown = (tmp_path / "fund_agent_report.md").read_text(encoding="utf-8")
    assert exit_code == 0
    assert "all_watchlist_missing" in markdown
    assert "数据质量等级: degraded" in markdown
