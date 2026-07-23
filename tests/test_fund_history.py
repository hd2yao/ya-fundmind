from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from fund_agent.cache import FundCache
from fund_agent.fund_history import FundHistoryService, FundHistoryUnavailable
from fund_agent.models import FundNavPoint
from fund_agent.providers import ProviderUnavailable


def _points(source: str = "akshare", count: int = 25) -> list[FundNavPoint]:
    return [
        FundNavPoint(
            code="021511",
            date=f"2026-06-{index + 1:02d}",
            unit_nav=1.0 + index / 100,
            daily_return=0.1,
            source=source,
            metadata=(
                {"series_kind": "fund_nav_history"}
                if source == "akshare"
                else {}
            ),
        )
        for index in range(count)
    ]


class NeverLiveProvider:
    def fetch_nav_history(self, code, **kwargs):
        raise AssertionError("fresh cache should prevent a live provider call")


def test_history_service_uses_fresh_akshare_cache_without_live_call(tmp_path):
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    cache = FundCache(tmp_path / "funds.sqlite")
    cache.upsert_nav_points(
        _points(source="akshare", count=5),
        as_of="2026-07-01",
        ttl_days=2,
        now=now,
    )
    cache.upsert_nav_points(
        _points(source="tiantian", count=5),
        as_of="2026-07-01",
        ttl_days=2,
        now=now,
    )
    service = FundHistoryService(cache=cache, provider=NeverLiveProvider())

    payload = service.get_history("021511", window="all", now=now)

    assert payload["point_count"] == 5
    assert payload["source"] == "cache:akshare"
    assert payload["stale"] is False
    assert payload["fallback_used"] is False
    assert {point["source"] for point in payload["points"]} == {"cache:akshare"}


class LiveProvider:
    def __init__(self):
        self.calls = 0

    def fetch_nav_history(self, code, **kwargs):
        self.calls += 1
        return _points(count=25)


def test_history_service_fetches_live_writes_cache_and_applies_window(tmp_path):
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    cache = FundCache(tmp_path / "funds.sqlite")
    provider = LiveProvider()
    service = FundHistoryService(
        cache=cache,
        provider=provider,
        cache_ttl_days=2,
    )

    payload = service.get_history("021511", window="1m", now=now)

    assert provider.calls == 1
    assert payload["range"] == "1m"
    assert payload["point_count"] == 20
    assert payload["points"][0]["date"] == "2026-06-06"
    assert payload["points"][-1]["date"] == "2026-06-25"
    assert payload["source"] == "akshare"
    assert payload["as_of"] == "2026-06-25"
    assert payload["data_quality_grade"] == "normal"
    assert len(cache.load_nav_points(code="021511", source="akshare", now=now)) == 25


def test_history_service_does_not_treat_latest_basic_nav_as_full_history(tmp_path):
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    cache = FundCache(tmp_path / "funds.sqlite")
    cache.upsert_nav_points(
        [
            FundNavPoint(
                code="021511",
                date="2026-07-01",
                unit_nav=1.25,
                source="akshare",
            )
        ],
        as_of="2026-07-01",
        ttl_days=2,
        now=now,
    )
    provider = LiveProvider()
    service = FundHistoryService(cache=cache, provider=provider)

    payload = service.get_history("021511", window="1m", now=now)

    assert provider.calls == 1
    assert payload["point_count"] == 20
    assert payload["points"][0]["date"] == "2026-06-06"


class FailingProvider:
    def fetch_nav_history(self, code, **kwargs):
        raise ProviderUnavailable("network down")


def test_history_service_falls_back_to_stale_akshare_cache(tmp_path):
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    cache = FundCache(tmp_path / "funds.sqlite")
    cache.upsert_nav_points(
        _points(count=5),
        as_of="2026-06-01",
        ttl_days=1,
        now=now - timedelta(days=10),
    )
    service = FundHistoryService(cache=cache, provider=FailingProvider())

    payload = service.get_history("021511", window="all", now=now)

    assert payload["source"] == "cache:akshare"
    assert payload["stale"] is True
    assert payload["fallback_used"] is True
    assert payload["fallback_reason"] == "network down"
    assert payload["data_quality_grade"] == "warning"
    assert any(warning["code"] == "live_fallback" for warning in payload["warnings"])
    assert any(warning["code"] == "stale_cache" for warning in payload["warnings"])


def test_history_service_fails_clearly_when_live_and_cache_are_unavailable(tmp_path):
    service = FundHistoryService(
        cache=FundCache(tmp_path / "funds.sqlite"),
        provider=FailingProvider(),
    )

    with pytest.raises(FundHistoryUnavailable, match="network down"):
        service.get_history("021511", window="6m")


@pytest.mark.parametrize("code,window", [("bad", "6m"), ("021511", "2y")])
def test_history_service_validates_code_and_window(tmp_path, code, window):
    service = FundHistoryService(
        cache=FundCache(tmp_path / "funds.sqlite"),
        provider=NeverLiveProvider(),
    )

    with pytest.raises(ValueError):
        service.get_history(code, window=window)
