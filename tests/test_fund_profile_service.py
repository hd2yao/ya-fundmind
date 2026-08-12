from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from fund_agent.cache import FundCache
from fund_agent.fund_profile import FundProfileService, FundProfileUnavailable
from fund_agent.models import FundFee, FundProfile, FundTradingRule
from fund_agent.providers import ProviderUnavailable


def _profile() -> FundProfile:
    return FundProfile(
        code="021511",
        name="示例混合A",
        fund_company="示例基金",
        source="akshare",
    )


def _rule() -> FundTradingRule:
    return FundTradingRule(
        code="021511",
        purchase_status="开放申购",
        redemption_status="开放赎回",
        source="akshare",
    )


def _fees() -> list[FundFee]:
    return [
        FundFee(
            code="021511",
            fee_type="申购费率（前端）",
            original_rate="1.20%",
            source="akshare",
        )
    ]


class NeverLiveProvider:
    def fetch_fund_profile(self, *args, **kwargs):
        raise AssertionError("fresh cache should prevent profile live access")

    def fetch_fund_trading_rule(self, *args, **kwargs):
        raise AssertionError("fresh cache should prevent rule live access")

    def fetch_fund_fees(self, *args, **kwargs):
        raise AssertionError("fresh cache should prevent fee live access")

    def fetch_fund_catalog(self, *args, **kwargs):
        raise AssertionError("detail service must never call the full catalog endpoint")

    def fetch_purchase_statuses(self, *args, **kwargs):
        raise AssertionError("detail service must never call fund_purchase_em")


def test_profile_service_uses_fresh_component_cache_without_live_call(tmp_path):
    now = datetime(2026, 7, 28, tzinfo=timezone.utc)
    cache = FundCache(tmp_path / "funds.sqlite")
    cache.upsert_fund_profiles([_profile()], as_of="2026-07-28", now=now)
    cache.upsert_fund_trading_rules([_rule()], as_of="2026-07-28", now=now)
    cache.replace_fund_fees("021511", _fees(), as_of="2026-07-28", now=now)
    service = FundProfileService(cache=cache, provider=NeverLiveProvider())

    bundle = service.get_profile("021511", now=now)

    assert bundle.code == "021511"
    assert bundle.profile is not None
    assert bundle.profile.source == "cache:akshare"
    assert bundle.trading_rule is not None
    assert len(bundle.fees) == 1
    assert bundle.data_status == "updated"
    assert bundle.warnings == ()


class LiveProvider:
    def __init__(self):
        self.calls = []

    def fetch_fund_profile(self, code, **kwargs):
        self.calls.append(("profile", code))
        return _profile()

    def fetch_fund_trading_rule(self, code, **kwargs):
        self.calls.append(("rule", code))
        return _rule()

    def fetch_fund_fees(self, code, **kwargs):
        self.calls.append(("fees", code))
        return _fees()

    def fetch_fund_catalog(self, *args, **kwargs):
        raise AssertionError("detail service must never call the full catalog endpoint")

    def fetch_purchase_statuses(self, *args, **kwargs):
        raise AssertionError("detail service must never call fund_purchase_em")


def test_profile_service_fetches_only_single_fund_components_and_writes_cache(tmp_path):
    now = datetime(2026, 7, 28, tzinfo=timezone.utc)
    cache = FundCache(tmp_path / "funds.sqlite")
    provider = LiveProvider()
    service = FundProfileService(cache=cache, provider=provider)

    bundle = service.get_profile(" 021511.OF ", as_of="2026-07-28", now=now)

    assert provider.calls == [
        ("profile", "021511"),
        ("rule", "021511"),
        ("fees", "021511"),
    ]
    assert bundle.data_status == "updated"
    assert cache.load_fund_profiles(code="021511", now=now)
    assert cache.load_fund_trading_rules(code="021511", now=now)
    assert cache.load_fund_fees(code="021511", now=now)


def test_purchase_snapshot_does_not_suppress_single_fund_rule_enrichment(tmp_path):
    now = datetime(2026, 7, 28, tzinfo=timezone.utc)
    cache = FundCache(tmp_path / "funds.sqlite")
    cache.upsert_fund_profiles([_profile()], as_of="2026-07-28", now=now)
    cache.replace_fund_fees("021511", _fees(), as_of="2026-07-28", now=now)
    cache.replace_purchase_snapshot(
        [_rule()],
        snapshot_id="purchase-v1",
        as_of="2026-07-28",
        now=now,
    )
    provider = LiveProvider()
    service = FundProfileService(cache=cache, provider=provider)

    bundle = service.get_profile("021511", now=now)

    assert provider.calls == [("rule", "021511")]
    assert bundle.trading_rule is not None
    assert cache.load_fund_trading_rules(code="021511", now=now)


class FailingProvider:
    def fetch_fund_profile(self, *args, **kwargs):
        raise ProviderUnavailable("profile endpoint down")

    def fetch_fund_trading_rule(self, *args, **kwargs):
        raise ProviderUnavailable("rule endpoint down")

    def fetch_fund_fees(self, *args, **kwargs):
        raise ProviderUnavailable("fee endpoint down")

    def fetch_fund_catalog(self, *args, **kwargs):
        raise AssertionError("detail service must never call the full catalog endpoint")

    def fetch_purchase_statuses(self, *args, **kwargs):
        raise AssertionError("detail service must never call fund_purchase_em")


def test_profile_service_falls_back_to_stale_same_component_cache(tmp_path):
    now = datetime(2026, 7, 28, tzinfo=timezone.utc)
    old_now = now - timedelta(days=10)
    cache = FundCache(tmp_path / "funds.sqlite")
    cache.upsert_fund_profiles([_profile()], as_of="2026-07-18", ttl_days=1, now=old_now)
    cache.upsert_fund_trading_rules([_rule()], as_of="2026-07-18", ttl_days=1, now=old_now)
    cache.replace_fund_fees("021511", _fees(), as_of="2026-07-18", ttl_days=1, now=old_now)
    service = FundProfileService(cache=cache, provider=FailingProvider())

    bundle = service.get_profile("021511", now=now)

    assert bundle.data_status == "limited"
    assert bundle.profile is not None and bundle.profile.stale is True
    assert bundle.trading_rule is not None and bundle.trading_rule.stale is True
    assert bundle.fees[0].stale is True
    assert any(item["code"] == "live_fallback" for item in bundle.warnings)


def test_profile_service_fails_clearly_without_live_or_cache(tmp_path):
    service = FundProfileService(
        cache=FundCache(tmp_path / "funds.sqlite"),
        provider=FailingProvider(),
    )

    with pytest.raises(FundProfileUnavailable, match="profile endpoint down"):
        service.get_profile("021511")


@pytest.mark.parametrize("code", ["bad", "12345", "ABCDEF"])
def test_profile_service_validates_six_digit_code(tmp_path, code):
    service = FundProfileService(
        cache=FundCache(tmp_path / "funds.sqlite"),
        provider=NeverLiveProvider(),
    )

    with pytest.raises(ValueError, match="six-digit"):
        service.get_profile(code)
