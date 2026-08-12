from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from .cache import FundCache
from .models import FundFee, FundProfile, FundProfileBundle, FundTradingRule
from .providers import ProviderUnavailable, normalize_fund_code


class FundProfileUnavailable(RuntimeError):
    """Raised when neither live nor cached profile components are available."""


class FundProfileService:
    def __init__(
        self,
        *,
        cache: FundCache,
        provider,
        cache_ttl_days: int = 7,
    ):
        self.cache = cache
        self.provider = provider
        self.cache_ttl_days = cache_ttl_days

    def get_profile(
        self,
        code: str,
        *,
        as_of: str | None = None,
        now: datetime | None = None,
    ) -> FundProfileBundle:
        resolved_code = normalize_fund_code(code)
        if len(resolved_code) != 6 or not resolved_code.isdigit():
            raise ValueError("profile requires a six-digit fund code")
        resolved_now = _utc_now(now)
        resolved_as_of = as_of or resolved_now.date().isoformat()

        catalog = _first_or_none(
            self.cache.load_catalog_entries(code=resolved_code, now=resolved_now)
        )
        if catalog is None:
            catalog = _first_or_none(
                self.cache.load_catalog_entries(
                    code=resolved_code,
                    allow_stale=True,
                    now=resolved_now,
                )
            )

        profile = _first_or_none(
            self.cache.load_fund_profiles(code=resolved_code, now=resolved_now)
        )
        trading_rule = _first_or_none(
            self.cache.load_fund_trading_rules(code=resolved_code, now=resolved_now)
        )
        purchase_snapshot_rule = _first_or_none(
            self.cache.load_purchase_statuses(code=resolved_code, now=resolved_now)
        )
        fees = tuple(self.cache.load_fund_fees(code=resolved_code, now=resolved_now))

        if profile is not None and trading_rule is not None and fees:
            return _bundle(
                code=resolved_code,
                catalog=catalog,
                profile=profile,
                trading_rule=trading_rule,
                fees=fees,
                warnings=(),
            )

        warnings: list[dict[str, str]] = []
        failures: list[str] = []
        if profile is None:
            try:
                live_profile = self.provider.fetch_fund_profile(
                    resolved_code,
                    as_of=resolved_as_of,
                )
            except ProviderUnavailable as exc:
                failures.append(str(exc))
                warnings.append(_fallback_warning("profile", exc))
            else:
                profile = _stamp_profile_component(
                    live_profile,
                    as_of=resolved_as_of,
                    now=resolved_now,
                    ttl_days=self.cache_ttl_days,
                )
                self.cache.upsert_fund_profiles(
                    [profile],
                    as_of=resolved_as_of,
                    ttl_days=self.cache_ttl_days,
                    now=resolved_now,
                )

        if trading_rule is None:
            try:
                live_rule = self.provider.fetch_fund_trading_rule(
                    resolved_code,
                    as_of=resolved_as_of,
                )
            except ProviderUnavailable as exc:
                failures.append(str(exc))
                warnings.append(_fallback_warning("trading_rule", exc))
                trading_rule = purchase_snapshot_rule
            else:
                trading_rule = _stamp_rule_component(
                    live_rule,
                    as_of=resolved_as_of,
                    now=resolved_now,
                    ttl_days=self.cache_ttl_days,
                )
                self.cache.upsert_fund_trading_rules(
                    [trading_rule],
                    as_of=resolved_as_of,
                    ttl_days=self.cache_ttl_days,
                    now=resolved_now,
                )

        if not fees:
            try:
                live_fees = self.provider.fetch_fund_fees(
                    resolved_code,
                    as_of=resolved_as_of,
                )
            except ProviderUnavailable as exc:
                failures.append(str(exc))
                warnings.append(_fallback_warning("fees", exc))
            else:
                fees = tuple(
                    _stamp_fee_component(
                        fee,
                        as_of=resolved_as_of,
                        now=resolved_now,
                        ttl_days=self.cache_ttl_days,
                    )
                    for fee in live_fees
                )
                self.cache.replace_fund_fees(
                    resolved_code,
                    fees,
                    as_of=resolved_as_of,
                    ttl_days=self.cache_ttl_days,
                    now=resolved_now,
                )

        fallback_used = bool(failures)
        if profile is None:
            profile = _first_or_none(
                self.cache.load_fund_profiles(
                    code=resolved_code,
                    allow_stale=True,
                    now=resolved_now,
                )
            )
        if trading_rule is None:
            trading_rule = _first_or_none(
                self.cache.load_fund_trading_rules(
                    code=resolved_code,
                    allow_stale=True,
                    now=resolved_now,
                )
            )
            if trading_rule is None:
                trading_rule = _first_or_none(
                    self.cache.load_purchase_statuses(
                        code=resolved_code,
                        allow_stale=True,
                        now=resolved_now,
                    )
                )
        if not fees:
            fees = tuple(
                self.cache.load_fund_fees(
                    code=resolved_code,
                    allow_stale=True,
                    now=resolved_now,
                )
            )

        if profile is None and trading_rule is None and not fees:
            reason = failures[0] if failures else "no fund profile components are available"
            raise FundProfileUnavailable(reason)

        if fallback_used:
            warnings.append(
                {
                    "code": "stale_cache" if _has_stale(profile, trading_rule, fees) else "partial_profile",
                    "message": "基金资料仅部分可用，已保留同类缓存或已取得组件。",
                }
            )
        return _bundle(
            code=resolved_code,
            catalog=catalog,
            profile=profile,
            trading_rule=trading_rule,
            fees=fees,
            warnings=tuple(warnings),
        )


def _bundle(
    *,
    code: str,
    catalog,
    profile: FundProfile | None,
    trading_rule: FundTradingRule | None,
    fees: tuple[FundFee, ...],
    warnings: tuple[dict[str, str], ...],
) -> FundProfileBundle:
    profile_status = "updated" if profile is not None and not profile.stale else "limited" if profile else "unavailable"
    trading_status = (
        "updated"
        if trading_rule is not None and not trading_rule.stale
        else "limited" if trading_rule else "unavailable"
    )
    fee_status = (
        "updated"
        if fees and not any(fee.stale for fee in fees)
        else "limited" if fees else "unavailable"
    )
    complete = profile_status == trading_status == fee_status == "updated"
    return FundProfileBundle(
        code=code,
        catalog=catalog,
        profile=profile,
        trading_rule=trading_rule,
        fees=fees,
        data_status="updated" if complete and not warnings else "limited",
        profile_status=profile_status,
        trading_status=trading_status,
        fee_status=fee_status,
        warnings=warnings,
    )


def _stamp_profile_component(
    profile: FundProfile,
    *,
    as_of: str,
    now: datetime,
    ttl_days: int,
) -> FundProfile:
    return replace(
        profile,
        as_of=profile.as_of or as_of,
        updated_at=profile.updated_at or now.isoformat(),
        expires_at=profile.expires_at or (now + timedelta(days=ttl_days)).isoformat(),
        stale=False,
    )


def _stamp_rule_component(
    rule: FundTradingRule,
    *,
    as_of: str,
    now: datetime,
    ttl_days: int,
) -> FundTradingRule:
    return replace(
        rule,
        as_of=rule.as_of or as_of,
        updated_at=rule.updated_at or now.isoformat(),
        expires_at=rule.expires_at or (now + timedelta(days=ttl_days)).isoformat(),
        stale=False,
    )


def _stamp_fee_component(
    fee: FundFee,
    *,
    as_of: str,
    now: datetime,
    ttl_days: int,
) -> FundFee:
    return replace(
        fee,
        as_of=fee.as_of or as_of,
        updated_at=fee.updated_at or now.isoformat(),
        expires_at=fee.expires_at or (now + timedelta(days=ttl_days)).isoformat(),
        stale=False,
    )


def _fallback_warning(component: str, exc: Exception) -> dict[str, str]:
    return {
        "code": "live_fallback",
        "component": component,
        "message": str(exc),
    }


def _has_stale(
    profile: FundProfile | None,
    trading_rule: FundTradingRule | None,
    fees: tuple[FundFee, ...],
) -> bool:
    return bool(
        (profile is not None and profile.stale)
        or (trading_rule is not None and trading_rule.stale)
        or any(fee.stale for fee in fees)
    )


def _first_or_none(items):
    return items[0] if items else None


def _utc_now(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
