from datetime import datetime, timezone

from fund_agent.cache import FundCache
from fund_agent.models import FundRecord
from fund_agent.providers import AkshareProvider


class FailingAkshare:
    def fund_open_fund_rank_em(self, symbol):
        raise RuntimeError("network down")


def test_akshare_provider_falls_back_to_cached_funds_with_reason(tmp_path):
    cache = FundCache(tmp_path / "funds.sqlite")
    cache.upsert_funds(
        [
            FundRecord(
                code="510300",
                name="沪深300ETF",
                category="ETF",
                nav=4.01,
                nav_date="2026-06-21",
                source="akshare",
            )
        ],
        as_of="2026-06-22",
        ttl_days=-1,
        now=datetime(2026, 6, 22, tzinfo=timezone.utc),
    )
    provider = AkshareProvider(
        ak_module=FailingAkshare(),
        cache=cache,
        allow_stale_cache=True,
    )

    funds = provider.fetch_funds(as_of="2026-06-22")

    assert len(funds) == 1
    assert funds[0].source == "cache:akshare"
    assert funds[0].metadata["stale"] is True
    assert funds[0].metadata["cache_as_of"] == "2026-06-22"
    assert funds[0].metadata["fallback_provider"] == "akshare"
    assert "network down" in funds[0].metadata["fallback_reason"]

