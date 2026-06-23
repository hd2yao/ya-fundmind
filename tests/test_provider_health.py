from pathlib import Path

from fund_agent.cache import FundCache
from fund_agent.cli import main
from fund_agent.models import FundRecord, ProviderHealth
from fund_agent.providers import AkshareProvider


class FakeDataFrame:
    def __init__(self, rows):
        self._rows = rows

    def iterrows(self):
        return iter(self._rows)


class BadRow:
    def get(self, key):
        raise ValueError(f"bad field: {key}")


class HealthAkshare:
    __version__ = "9.9.9"

    def fund_open_fund_rank_em(self, symbol):
        return FakeDataFrame(
            [
                (
                    0,
                    {
                        "基金代码": "000311",
                        "基金简称": "沪深300增强A",
                        "单位净值": "1.25",
                        "近1月": "2.5%",
                    },
                ),
                (1, {"基金代码": "", "基金简称": ""}),
                (2, BadRow()),
            ]
        )

    def fund_etf_spot_em(self):
        return FakeDataFrame(
            [
                (
                    0,
                    {
                        "代码": "510300",
                        "名称": "沪深300ETF",
                        "最新价": "5.08",
                        "IOPV实时估值": "5.07",
                        "总市值": "10000000000",
                        "数据日期": "2026-06-23",
                    },
                )
            ]
        )


def test_akshare_provider_records_live_health_and_cache_write_count(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    provider = AkshareProvider(ak_module=HealthAkshare(), cache=cache)

    funds = provider.fetch_funds(as_of="2026-06-23")

    health = provider.last_health
    assert len(funds) == 2
    assert health is not None
    assert health.provider == "akshare"
    assert health.provider_version == "9.9.9"
    assert health.live_row_count == 4
    assert health.mapped_row_count == 2
    assert health.skipped_row_count == 2
    assert health.cache_write_count == 2
    assert health.fallback_used is False
    assert health.duration_ms >= 0
    assert any(warning.code == "row_skipped" for warning in health.warnings)


class FailingAkshare:
    __version__ = "9.9.9"

    def fund_open_fund_rank_em(self, symbol):
        raise RuntimeError("network down")

    def fund_etf_spot_em(self):
        raise RuntimeError("etf down")


def test_akshare_provider_records_fallback_warning(tmp_path):
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
    )
    provider = AkshareProvider(ak_module=FailingAkshare(), cache=cache)

    funds = provider.fetch_funds(as_of="2026-06-23")

    health = provider.last_health
    assert funds
    assert health is not None
    assert health.fallback_used is True
    assert health.fallback_source == "cache"
    assert "network down" in str(health.fallback_reason)
    assert any(warning.code == "fallback_cache" for warning in health.warnings)


def test_cli_records_watchlist_missing_warning(monkeypatch, tmp_path):
    watchlist = tmp_path / "watchlist.yaml"
    watchlist.write_text(
        """
funds:
  - code: 510300
  - code: 999999
""",
        encoding="utf-8",
    )

    class OneFundProvider:
        def __init__(self, **kwargs):
            self.last_health = ProviderHealth(
                provider="akshare",
                started_at="2026-06-23T00:00:00+00:00",
                finished_at="2026-06-23T00:00:01+00:00",
                duration_ms=1000,
                live_row_count=1,
                mapped_row_count=1,
            )

        def fetch_funds(self, *, as_of=None):
            return [
                FundRecord(
                    code="510300",
                    name="沪深300ETF",
                    category="ETF",
                    nav=5.0,
                    source="akshare",
                )
            ]

    monkeypatch.setattr("fund_agent.cli.AkshareProvider", OneFundProvider)

    exit_code = main(
        [
            "daily",
            "--provider",
            "akshare",
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
    assert "数据源健康状态" in markdown
    assert "watchlist_missing" in markdown
    assert "999999" in markdown
