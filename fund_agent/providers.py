from __future__ import annotations

import json
import contextlib
import io
import concurrent.futures
import os
import re
import signal
import socket
import threading
import time
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from .cache import FundCache
from .models import (
    FundCatalogEntry,
    FundFee,
    FundDetail,
    FundNavPoint,
    FundProfile,
    FundRecord,
    FundTradingRule,
    MarketEntity,
    MarketSeriesPoint,
    ProviderEndpointTrace,
    ProviderHealth,
    ProviderWarning,
)
from .portfolio import PortfolioHolding


class ProviderUnavailable(RuntimeError):
    """Raised when an optional live provider is not available."""


class ProviderCallTimeout(TimeoutError):
    """Raised when a live provider call exceeds its configured deadline."""


class TiantianProviderError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


class FundProvider(Protocol):
    def fetch_funds(self, *, as_of: str | None = None) -> list[FundRecord]:
        """Return normalized fund records."""


def normalize_fund_code(value: object) -> str:
    text = str(value or "").strip()
    if "." in text:
        text = text.split(".", 1)[0]
    if len(text) == 8 and text[:2].isalpha() and text[2:].isdigit():
        return text[2:]
    return text


def _require_fund_code(value: object) -> str:
    code = normalize_fund_code(value)
    if len(code) != 6 or not code.isdigit():
        raise ValueError("a six-digit fund code is required")
    return code


def normalize_fund_name(value: object) -> str:
    return str(value or "").strip()


def normalize_fund_category(value: object) -> str:
    text = str(value or "").strip()
    return text or "基金"


def _akshare_index_symbol(symbol: str) -> str:
    return f"sz{symbol}" if symbol.startswith("399") else f"sh{symbol}"


class FixtureProvider:
    def __init__(self, funds_path: Path | str = Path("data/fixtures/funds.json")):
        self.funds_path = Path(funds_path)
        self.last_health: ProviderHealth | None = None

    def fetch_funds(self, *, as_of: str | None = None) -> list[FundRecord]:
        started_at = _utc_now()
        payload = json.loads(self.funds_path.read_text(encoding="utf-8"))
        funds = [_fund_from_mapping(item, source="fixture") for item in payload]
        self.last_health = _build_health(
            provider="fixture",
            provider_version=None,
            started_at=started_at,
            live_row_count=len(payload),
            mapped_row_count=len(funds),
        )
        return funds


class AkshareProvider:
    """Optional live provider.

    The MVP keeps AKShare behind a boundary so the demo and tests never need
    network access. When AKShare is not installed, callers receive a clear
    ProviderUnavailable error instead of an import failure.
    """

    def __init__(
        self,
        fund_type: str = "全部",
        *,
        ak_module=None,
        cache: FundCache | None = None,
        allow_stale_cache: bool = True,
        cache_ttl_days: int = 1,
        verbose: bool = False,
        timeout_seconds: float = 20.0,
        retry_count: int = 0,
        retry_backoff_seconds: float = 0.0,
    ):
        self.fund_type = fund_type
        self.cache = cache
        self.allow_stale_cache = allow_stale_cache
        self.cache_ttl_days = cache_ttl_days
        self.verbose = verbose
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count
        self.retry_backoff_seconds = retry_backoff_seconds
        self.last_health: ProviderHealth | None = None
        if ak_module is not None:
            self._ak = ak_module
        else:
            try:
                import akshare as ak  # type: ignore
            except Exception:  # pragma: no cover - depends on local environment
                self._ak = None
            else:  # pragma: no cover - live provider is smoke-tested manually
                self._ak = ak

    @property
    def available(self) -> bool:
        return self._ak is not None

    @property
    def provider_version(self) -> str | None:
        if self._ak is None:
            return None
        return str(getattr(self._ak, "__version__", "") or "unknown")

    def fetch_funds(self, *, as_of: str | None = None) -> list[FundRecord]:
        started_at = _utc_now()
        resolved_as_of = as_of or date.today().isoformat()
        if self._ak is None:
            return self._fallback_to_cache(
                "AKShare is not installed",
                as_of=resolved_as_of,
                started_at=started_at,
            )
        errors: list[str] = []
        warnings: list[ProviderWarning] = []
        live_row_count = 0
        mapped_row_count = 0
        skipped_row_count = 0
        endpoints: list[ProviderEndpointTrace] = []
        funds: list[FundRecord] = []
        result = self._call_akshare("fund_open_fund_rank_em", symbol=self.fund_type)
        endpoints.append(result.trace)
        if not result.success:
            message = f"fund_open_fund_rank_em: {result.error}"
            errors.append(message)
            warnings.append(ProviderWarning(code="live_fetch_error", message=message))
        else:
            mapping = _funds_from_rows(result.data, _fund_from_akshare_row, endpoint="fund_open_fund_rank_em")
            live_row_count += mapping.live_row_count
            mapped_row_count += len(mapping.funds)
            skipped_row_count += mapping.skipped_row_count
            warnings.extend(mapping.warnings)
            funds.extend(mapping.funds)
            endpoints[-1] = replace(
                endpoints[-1],
                live_row_count=mapping.live_row_count,
                mapped_row_count=len(mapping.funds),
                skipped_row_count=mapping.skipped_row_count,
            )
        if hasattr(self._ak, "fund_etf_spot_em"):
            result = self._call_akshare("fund_etf_spot_em")
            endpoints.append(result.trace)
            if not result.success:
                message = f"fund_etf_spot_em: {result.error}"
                errors.append(message)
                warnings.append(ProviderWarning(code="live_fetch_error", message=message))
            else:
                mapping = _funds_from_rows(result.data, _fund_from_akshare_etf_row, endpoint="fund_etf_spot_em")
                live_row_count += mapping.live_row_count
                mapped_row_count += len(mapping.funds)
                skipped_row_count += mapping.skipped_row_count
                warnings.extend(mapping.warnings)
                funds.extend(mapping.funds)
                endpoints[-1] = replace(
                    endpoints[-1],
                    live_row_count=mapping.live_row_count,
                    mapped_row_count=len(mapping.funds),
                    skipped_row_count=mapping.skipped_row_count,
                )
        updated_at = _utc_now()
        expires_at = updated_at + timedelta(days=self.cache_ttl_days)
        normalized_funds = [
            _with_provider_metadata(
                fund,
                as_of=resolved_as_of,
                provider="akshare",
                updated_at=updated_at,
                expires_at=expires_at,
            )
            for fund in funds
            if fund.code and fund.name
        ]
        normalized_funds = _dedupe_funds(normalized_funds)
        if not normalized_funds:
            return self._fallback_to_cache(
                "; ".join(errors) if errors else "AKShare returned no valid fund rows",
                as_of=resolved_as_of,
                started_at=started_at,
                live_row_count=live_row_count,
                skipped_row_count=skipped_row_count,
                warnings=tuple(warnings),
                endpoints=tuple(endpoints),
            )
        cache_write_count = 0
        if self.cache is not None and normalized_funds:
            self.cache.upsert_funds(
                normalized_funds,
                as_of=resolved_as_of,
                ttl_days=self.cache_ttl_days,
                now=updated_at,
            )
            cache_write_count = len(normalized_funds)
        self.last_health = _build_health(
            provider="akshare",
            provider_version=self.provider_version,
            started_at=started_at,
            live_row_count=live_row_count,
            mapped_row_count=mapped_row_count,
            skipped_row_count=skipped_row_count,
            cache_write_count=cache_write_count,
            warnings=tuple(warnings),
            endpoints=tuple(endpoints),
        )
        return normalized_funds

    def fetch_fund_catalog(
        self,
        *,
        as_of: str | None = None,
    ) -> list[FundCatalogEntry]:
        started_at = _utc_now()
        resolved_as_of = as_of or date.today().isoformat()
        if self._ak is None:
            raise ProviderUnavailable("AKShare is not installed")
        endpoint_specs = (
            ("fund_name_em", {}, _fund_catalog_from_name_row),
            (
                "fund_open_fund_rank_em",
                {"symbol": self.fund_type},
                _fund_catalog_from_rank_row,
            ),
            ("fund_etf_spot_em", {}, _fund_catalog_from_etf_row),
        )
        entries: list[FundCatalogEntry] = []
        warnings: list[ProviderWarning] = []
        endpoint_traces: list[ProviderEndpointTrace] = []
        live_row_count = 0
        skipped_row_count = 0
        for endpoint, kwargs, mapper in endpoint_specs:
            result = self._call_akshare(endpoint, **kwargs)
            endpoint_traces.append(result.trace)
            if not result.success:
                warnings.append(
                    ProviderWarning(
                        code="live_fetch_error",
                        message=f"{endpoint}: {result.error}",
                    )
                )
                continue
            mapping = _fund_catalog_entries_from_rows(
                result.data,
                mapper,
                endpoint=endpoint,
            )
            live_row_count += mapping.live_row_count
            skipped_row_count += mapping.skipped_row_count
            warnings.extend(mapping.warnings)
            entries.extend(mapping.entries)
            endpoint_traces[-1] = replace(
                endpoint_traces[-1],
                live_row_count=mapping.live_row_count,
                mapped_row_count=len(mapping.entries),
                skipped_row_count=mapping.skipped_row_count,
            )
        normalized = _dedupe_catalog_entries(entries)
        if not normalized:
            self.last_health = _build_health(
                provider="akshare",
                provider_version=self.provider_version,
                started_at=started_at,
                live_row_count=live_row_count,
                skipped_row_count=skipped_row_count,
                endpoints=tuple(endpoint_traces),
                warnings=tuple(warnings),
            )
            raise ProviderUnavailable("AKShare returned no valid fund catalog rows")
        updated_at = _utc_now()
        expires_at = updated_at + timedelta(days=self.cache_ttl_days)
        normalized = [
            replace(
                entry,
                as_of=resolved_as_of,
                updated_at=updated_at.isoformat(),
                expires_at=expires_at.isoformat(),
                stale=False,
            )
            for entry in normalized
        ]
        self.last_health = _build_health(
            provider="akshare",
            provider_version=self.provider_version,
            started_at=started_at,
            live_row_count=live_row_count,
            mapped_row_count=len(normalized),
            skipped_row_count=skipped_row_count,
            endpoints=tuple(endpoint_traces),
            warnings=tuple(warnings),
        )
        return normalized

    def fetch_purchase_statuses(
        self,
        *,
        as_of: str | None = None,
    ) -> list[FundTradingRule]:
        started_at = _utc_now()
        resolved_as_of = as_of or date.today().isoformat()
        if self._ak is None:
            raise ProviderUnavailable("AKShare is not installed")
        result = self._call_akshare("fund_purchase_em")
        if not result.success:
            self.last_health = _build_health(
                provider="akshare",
                provider_version=self.provider_version,
                started_at=started_at,
                endpoints=(result.trace,),
                warnings=(
                    ProviderWarning(
                        code="live_fetch_error",
                        message=f"fund_purchase_em: {result.error}",
                        severity="critical",
                    ),
                ),
            )
            raise ProviderUnavailable(f"AKShare purchase status fetch failed: {result.error}")
        mapping = _purchase_rules_from_rows(result.data, endpoint="fund_purchase_em")
        endpoint_trace = replace(
            result.trace,
            live_row_count=mapping.live_row_count,
            mapped_row_count=len(mapping.rules),
            skipped_row_count=mapping.skipped_row_count,
        )
        if not mapping.rules:
            self.last_health = _build_health(
                provider="akshare",
                provider_version=self.provider_version,
                started_at=started_at,
                live_row_count=mapping.live_row_count,
                skipped_row_count=mapping.skipped_row_count,
                endpoints=(endpoint_trace,),
                warnings=mapping.warnings,
            )
            raise ProviderUnavailable("AKShare returned no valid purchase status rows")
        updated_at = _utc_now()
        expires_at = updated_at + timedelta(days=self.cache_ttl_days)
        rules = [
            replace(
                rule,
                as_of=resolved_as_of,
                updated_at=updated_at.isoformat(),
                expires_at=expires_at.isoformat(),
                stale=False,
            )
            for rule in mapping.rules
        ]
        self.last_health = _build_health(
            provider="akshare",
            provider_version=self.provider_version,
            started_at=started_at,
            live_row_count=mapping.live_row_count,
            mapped_row_count=len(rules),
            skipped_row_count=mapping.skipped_row_count,
            endpoints=(endpoint_trace,),
            warnings=mapping.warnings,
        )
        return rules

    def fetch_fund_profile(
        self,
        code: str,
        *,
        as_of: str | None = None,
    ) -> FundProfile:
        started_at = _utc_now()
        resolved_code = _require_fund_code(code)
        resolved_as_of = as_of or date.today().isoformat()
        if self._ak is None:
            raise ProviderUnavailable("AKShare is not installed")
        result = self._call_akshare("fund_overview_em", symbol=resolved_code)
        if not result.success:
            self._set_profile_failure_health(started_at, result.trace, result.error)
            raise ProviderUnavailable(f"AKShare fund overview fetch failed: {result.error}")
        iterrows = getattr(result.data, "iterrows", None)
        if not callable(iterrows):
            self._set_profile_failure_health(
                started_at,
                replace(result.trace, success=False, error="invalid_response"),
                "invalid_response",
            )
            raise ProviderUnavailable("AKShare fund overview returned a non-tabular response")
        live_row_count = 0
        skipped_row_count = 0
        warnings: list[ProviderWarning] = []
        profile: FundProfile | None = None
        for row_index, row in iterrows():
            live_row_count += 1
            try:
                profile = _fund_profile_from_akshare_row(row, code=resolved_code)
            except Exception as exc:
                skipped_row_count += 1
                warnings.append(
                    ProviderWarning(
                        code="skipped_rows",
                        message=f"fund_overview_em row {row_index} skipped: {exc}",
                        details={"endpoint": "fund_overview_em", "row_index": row_index},
                    )
                )
                continue
            break
        endpoint_trace = replace(
            result.trace,
            live_row_count=live_row_count,
            mapped_row_count=1 if profile is not None else 0,
            skipped_row_count=skipped_row_count,
        )
        if profile is None:
            self.last_health = _build_health(
                provider="akshare",
                provider_version=self.provider_version,
                started_at=started_at,
                live_row_count=live_row_count,
                skipped_row_count=skipped_row_count,
                endpoints=(endpoint_trace,),
                warnings=tuple(warnings),
            )
            raise ProviderUnavailable("AKShare returned no valid fund overview row")
        updated_at = _utc_now()
        profile = replace(
            profile,
            as_of=resolved_as_of,
            updated_at=updated_at.isoformat(),
            expires_at=(updated_at + timedelta(days=self.cache_ttl_days)).isoformat(),
            stale=False,
        )
        self.last_health = _build_health(
            provider="akshare",
            provider_version=self.provider_version,
            started_at=started_at,
            live_row_count=live_row_count,
            mapped_row_count=1,
            skipped_row_count=skipped_row_count,
            endpoints=(endpoint_trace,),
            warnings=tuple(warnings),
        )
        return profile

    def fetch_fund_trading_rule(
        self,
        code: str,
        *,
        as_of: str | None = None,
    ) -> FundTradingRule:
        started_at = _utc_now()
        resolved_code = _require_fund_code(code)
        resolved_as_of = as_of or date.today().isoformat()
        if self._ak is None:
            raise ProviderUnavailable("AKShare is not installed")
        indicators = ("交易状态", "申购与赎回金额", "交易确认日")
        values: dict[str, str | None] = {
            "purchase_status": None,
            "redemption_status": None,
            "next_open_date": None,
            "minimum_purchase_amount": None,
            "daily_purchase_limit": None,
            "confirmation_rule": None,
        }
        endpoint_traces: list[ProviderEndpointTrace] = []
        warnings: list[ProviderWarning] = []
        live_row_count = 0
        mapped_row_count = 0
        skipped_row_count = 0
        for indicator in indicators:
            result = self._call_akshare(
                "fund_fee_em",
                symbol=resolved_code,
                indicator=indicator,
            )
            endpoint_traces.append(result.trace)
            if not result.success:
                warnings.append(
                    ProviderWarning(
                        code="live_fetch_error",
                        message=f"fund_fee_em[{indicator}]: {result.error}",
                    )
                )
                continue
            counts = _merge_trading_rule_rows(result.data, values, indicator=indicator)
            live_row_count += counts[0]
            mapped_row_count += counts[1]
            skipped_row_count += counts[2]
            warnings.extend(counts[3])
            endpoint_traces[-1] = replace(
                endpoint_traces[-1],
                live_row_count=counts[0],
                mapped_row_count=counts[1],
                skipped_row_count=counts[2],
            )
        if not any(values.values()):
            self.last_health = _build_health(
                provider="akshare",
                provider_version=self.provider_version,
                started_at=started_at,
                live_row_count=live_row_count,
                skipped_row_count=skipped_row_count,
                endpoints=tuple(endpoint_traces),
                warnings=tuple(warnings),
            )
            raise ProviderUnavailable("AKShare returned no valid fund trading rule fields")
        updated_at = _utc_now()
        rule = FundTradingRule(
            code=resolved_code,
            **values,
            source="akshare",
            as_of=resolved_as_of,
            updated_at=updated_at.isoformat(),
            expires_at=(updated_at + timedelta(days=self.cache_ttl_days)).isoformat(),
            stale=False,
            metadata={"endpoint": "fund_fee_em", "indicators": indicators},
        )
        self.last_health = _build_health(
            provider="akshare",
            provider_version=self.provider_version,
            started_at=started_at,
            live_row_count=live_row_count,
            mapped_row_count=mapped_row_count,
            skipped_row_count=skipped_row_count,
            endpoints=tuple(endpoint_traces),
            warnings=tuple(warnings),
        )
        return rule

    def fetch_fund_fees(
        self,
        code: str,
        *,
        as_of: str | None = None,
        indicators: tuple[str, ...] = ("申购费率（前端）", "赎回费率", "运作费用"),
    ) -> list[FundFee]:
        started_at = _utc_now()
        resolved_code = _require_fund_code(code)
        resolved_as_of = as_of or date.today().isoformat()
        if self._ak is None:
            raise ProviderUnavailable("AKShare is not installed")
        fees: list[FundFee] = []
        warnings: list[ProviderWarning] = []
        endpoint_traces: list[ProviderEndpointTrace] = []
        live_row_count = 0
        skipped_row_count = 0
        for indicator in indicators:
            result = self._call_akshare(
                "fund_fee_em",
                symbol=resolved_code,
                indicator=indicator,
            )
            endpoint_traces.append(result.trace)
            if not result.success:
                warnings.append(
                    ProviderWarning(
                        code="live_fetch_error",
                        message=f"fund_fee_em[{indicator}]: {result.error}",
                    )
                )
                continue
            mapping = _fund_fees_from_akshare_rows(
                result.data,
                code=resolved_code,
                indicator=indicator,
            )
            live_row_count += mapping.live_row_count
            skipped_row_count += mapping.skipped_row_count
            warnings.extend(mapping.warnings)
            fees.extend(mapping.fees)
            endpoint_traces[-1] = replace(
                endpoint_traces[-1],
                live_row_count=mapping.live_row_count,
                mapped_row_count=len(mapping.fees),
                skipped_row_count=mapping.skipped_row_count,
            )
        if not fees:
            self.last_health = _build_health(
                provider="akshare",
                provider_version=self.provider_version,
                started_at=started_at,
                live_row_count=live_row_count,
                skipped_row_count=skipped_row_count,
                endpoints=tuple(endpoint_traces),
                warnings=tuple(warnings),
            )
            raise ProviderUnavailable("AKShare returned no valid fund fee rows")
        updated_at = _utc_now()
        normalized = [
            replace(
                fee,
                as_of=resolved_as_of,
                updated_at=updated_at.isoformat(),
                expires_at=(updated_at + timedelta(days=self.cache_ttl_days)).isoformat(),
                stale=False,
            )
            for fee in fees
        ]
        self.last_health = _build_health(
            provider="akshare",
            provider_version=self.provider_version,
            started_at=started_at,
            live_row_count=live_row_count,
            mapped_row_count=len(normalized),
            skipped_row_count=skipped_row_count,
            endpoints=tuple(endpoint_traces),
            warnings=tuple(warnings),
        )
        return normalized

    def _set_profile_failure_health(
        self,
        started_at: datetime,
        trace: ProviderEndpointTrace,
        error: str | None,
    ) -> None:
        self.last_health = _build_health(
            provider="akshare",
            provider_version=self.provider_version,
            started_at=started_at,
            endpoints=(trace,),
            warnings=(
                ProviderWarning(
                    code="live_fetch_error",
                    message=f"fund_overview_em: {error}",
                    severity="critical",
                ),
            ),
        )

    def fetch_nav_history(
        self,
        code: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        as_of: str | None = None,
    ) -> list[FundNavPoint]:
        started_at = _utc_now()
        resolved_code = normalize_fund_code(code)
        resolved_as_of = as_of or date.today().isoformat()
        if self._ak is None:
            reason = "AKShare is not installed"
            self.last_health = _build_health(
                provider="akshare",
                provider_version=self.provider_version,
                started_at=started_at,
                warnings=(
                    ProviderWarning(
                        code="live_fetch_error",
                        message=reason,
                        severity="critical",
                    ),
                ),
            )
            raise ProviderUnavailable(reason)

        result = self._call_akshare(
            "fund_open_fund_info_em",
            symbol=resolved_code,
            indicator="单位净值走势",
        )
        if not result.success:
            message = f"fund_open_fund_info_em: {result.error}"
            self.last_health = _build_health(
                provider="akshare",
                provider_version=self.provider_version,
                started_at=started_at,
                endpoints=(result.trace,),
                warnings=(
                    ProviderWarning(
                        code="live_fetch_error",
                        message=message,
                        severity="critical",
                    ),
                ),
            )
            raise ProviderUnavailable(f"AKShare fund history fetch failed: {message}")

        mapping = _nav_points_from_akshare_rows(
            result.data,
            code=resolved_code,
            endpoint="fund_open_fund_info_em",
        )
        endpoint_trace = replace(
            result.trace,
            live_row_count=mapping.live_row_count,
            mapped_row_count=len(mapping.nav_points),
            skipped_row_count=mapping.skipped_row_count,
        )
        if not mapping.nav_points:
            warning = ProviderWarning(
                code="empty_live_response",
                message=f"AKShare returned no valid NAV rows for {resolved_code}.",
                severity="critical",
            )
            self.last_health = _build_health(
                provider="akshare",
                provider_version=self.provider_version,
                started_at=started_at,
                live_row_count=mapping.live_row_count,
                skipped_row_count=mapping.skipped_row_count,
                endpoints=(endpoint_trace,),
                warnings=(*mapping.warnings, warning),
            )
            raise ProviderUnavailable(
                f"AKShare returned no valid NAV rows for {resolved_code}."
            )

        updated_at = _utc_now()
        expires_at = updated_at + timedelta(days=self.cache_ttl_days)
        normalized_points = [
            replace(
                point,
                updated_at=updated_at.isoformat(),
                metadata={
                    **point.metadata,
                    "provider": "akshare",
                    "series_kind": "fund_nav_history",
                    "as_of": resolved_as_of,
                    "updated_at": updated_at.isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "stale": False,
                },
            )
            for point in mapping.nav_points
        ]
        cache_write_count = 0
        if self.cache is not None:
            self.cache.upsert_nav_points(
                normalized_points,
                as_of=resolved_as_of,
                ttl_days=self.cache_ttl_days,
                now=updated_at,
            )
            cache_write_count = len(normalized_points)
        self.last_health = _build_health(
            provider="akshare",
            provider_version=self.provider_version,
            started_at=started_at,
            live_row_count=mapping.live_row_count,
            mapped_row_count=len(normalized_points),
            skipped_row_count=mapping.skipped_row_count,
            cache_write_count=cache_write_count,
            endpoints=(endpoint_trace,),
            warnings=mapping.warnings,
        )
        return [
            point
            for point in normalized_points
            if (start_date is None or point.date >= start_date)
            and (end_date is None or point.date <= end_date)
        ]

    def fetch_index_history(
        self,
        symbol: str,
        *,
        name: str,
        start_date: str | None = None,
        end_date: str | None = None,
        as_of: str | None = None,
    ) -> list[MarketSeriesPoint]:
        started_at = _utc_now()
        resolved_symbol = str(symbol).strip()
        resolved_as_of = as_of or date.today().isoformat()
        if self._ak is None:
            reason = "AKShare is not installed"
            self.last_health = _build_health(
                provider="akshare",
                provider_version=self.provider_version,
                started_at=started_at,
                warnings=(
                    ProviderWarning(
                        code="live_fetch_error",
                        message=reason,
                        severity="critical",
                    ),
                ),
            )
            raise ProviderUnavailable(reason)

        provider_symbol = _akshare_index_symbol(resolved_symbol)
        endpoints: list[ProviderEndpointTrace] = []
        warnings: list[ProviderWarning] = []
        live_row_count = 0
        skipped_row_count = 0
        result = self._call_akshare(
            "stock_zh_index_daily_em",
            symbol=provider_symbol,
            start_date=start_date or "19700101",
            end_date=end_date or resolved_as_of.replace("-", ""),
        )
        endpoints.append(result.trace)
        selected_endpoint = "stock_zh_index_daily_em"
        mapping = (
            _index_points_from_akshare_rows(
                result.data,
                symbol=resolved_symbol,
                name=name,
                endpoint=selected_endpoint,
            )
            if result.success
            else None
        )
        if mapping is not None:
            live_row_count += mapping.live_row_count
            skipped_row_count += mapping.skipped_row_count
            warnings.extend(mapping.warnings)
            endpoints[-1] = replace(
                endpoints[-1],
                live_row_count=mapping.live_row_count,
                mapped_row_count=len(mapping.points),
                skipped_row_count=mapping.skipped_row_count,
            )

        primary_unusable = not result.success or mapping is None or not mapping.points
        if primary_unusable and hasattr(self._ak, "stock_zh_index_daily"):
            primary_reason = (
                result.error
                if not result.success
                else "no valid rows returned"
            )
            warnings.append(
                ProviderWarning(
                    code="endpoint_fallback",
                    message=(
                        "stock_zh_index_daily_em was unavailable; "
                        "stock_zh_index_daily was used."
                    ),
                    severity="warning",
                    details={
                        "primary_endpoint": "stock_zh_index_daily_em",
                        "fallback_endpoint": "stock_zh_index_daily",
                        "reason": primary_reason,
                    },
                )
            )
            selected_endpoint = "stock_zh_index_daily"
            result = self._call_akshare(
                selected_endpoint,
                symbol=provider_symbol,
            )
            endpoints.append(result.trace)
            mapping = (
                _index_points_from_akshare_rows(
                    result.data,
                    symbol=resolved_symbol,
                    name=name,
                    endpoint=selected_endpoint,
                )
                if result.success
                else None
            )
            if mapping is not None:
                live_row_count += mapping.live_row_count
                skipped_row_count += mapping.skipped_row_count
                warnings.extend(mapping.warnings)
                endpoints[-1] = replace(
                    endpoints[-1],
                    live_row_count=mapping.live_row_count,
                    mapped_row_count=len(mapping.points),
                    skipped_row_count=mapping.skipped_row_count,
                )

        if not result.success:
            message = f"{selected_endpoint}: {result.error}"
            self.last_health = _build_health(
                provider="akshare",
                provider_version=self.provider_version,
                started_at=started_at,
                live_row_count=live_row_count,
                skipped_row_count=skipped_row_count,
                endpoints=tuple(endpoints),
                warnings=(
                    *warnings,
                    ProviderWarning(
                        code="live_fetch_error",
                        message=message,
                        severity="critical",
                    ),
                ),
            )
            raise ProviderUnavailable(f"AKShare index history fetch failed: {message}")

        if mapping is None or not mapping.points:
            warning = ProviderWarning(
                code="empty_live_response",
                message=f"AKShare returned no valid index rows for {resolved_symbol}.",
                severity="critical",
            )
            self.last_health = _build_health(
                provider="akshare",
                provider_version=self.provider_version,
                started_at=started_at,
                live_row_count=live_row_count,
                skipped_row_count=skipped_row_count,
                endpoints=tuple(endpoints),
                warnings=(*warnings, warning),
            )
            raise ProviderUnavailable(
                f"AKShare returned no valid index rows for {resolved_symbol}."
            )

        range_start = (start_date or "19700101").replace("-", "")
        range_end = (end_date or resolved_as_of).replace("-", "")
        selected_points = [
            point
            for point in mapping.points
            if range_start <= point.date.replace("-", "") <= range_end
        ]
        if not selected_points:
            warning = ProviderWarning(
                code="empty_live_response",
                message=(
                    f"AKShare returned no index rows for {resolved_symbol} "
                    f"between {range_start} and {range_end}."
                ),
                severity="critical",
            )
            self.last_health = _build_health(
                provider="akshare",
                provider_version=self.provider_version,
                started_at=started_at,
                live_row_count=live_row_count,
                skipped_row_count=skipped_row_count,
                endpoints=tuple(endpoints),
                warnings=(*warnings, warning),
            )
            raise ProviderUnavailable(warning.message)

        updated_at = _utc_now()
        expires_at = updated_at + timedelta(days=self.cache_ttl_days)
        normalized_points = [
            replace(
                point,
                updated_at=updated_at.isoformat(),
                metadata={
                    **point.metadata,
                    "provider": "akshare",
                    "series_kind": "market_index_history",
                    "as_of": resolved_as_of,
                    "updated_at": updated_at.isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "stale": False,
                },
            )
            for point in selected_points
        ]
        cache_write_count = 0
        if self.cache is not None:
            self.cache.upsert_market_series(
                normalized_points,
                as_of=resolved_as_of,
                ttl_days=self.cache_ttl_days,
                now=updated_at,
            )
            cache_write_count = len(normalized_points)
        self.last_health = _build_health(
            provider="akshare",
            provider_version=self.provider_version,
            started_at=started_at,
            live_row_count=live_row_count,
            mapped_row_count=len(normalized_points),
            skipped_row_count=skipped_row_count,
            cache_write_count=cache_write_count,
            endpoints=tuple(endpoints),
            warnings=tuple(warnings),
        )
        return normalized_points

    def fetch_industry_boards(
        self,
        *,
        as_of: str | None = None,
    ) -> list[MarketEntity]:
        started_at = _utc_now()
        resolved_as_of = as_of or date.today().isoformat()
        endpoint = "stock_board_industry_name_em"
        if self._ak is None:
            reason = "AKShare is not installed"
            self.last_health = _build_health(
                provider="akshare",
                provider_version=self.provider_version,
                started_at=started_at,
                warnings=(
                    ProviderWarning(
                        code="live_fetch_error",
                        message=reason,
                        severity="critical",
                    ),
                ),
            )
            raise ProviderUnavailable(reason)

        result = self._call_akshare(endpoint)
        mapping = (
            _industry_entities_from_akshare_rows(
                result.data,
                endpoint=endpoint,
                as_of=resolved_as_of,
            )
            if result.success
            else None
        )
        endpoint_trace = result.trace
        if mapping is not None:
            endpoint_trace = replace(
                endpoint_trace,
                live_row_count=mapping.live_row_count,
                mapped_row_count=len(mapping.entities),
                skipped_row_count=mapping.skipped_row_count,
            )
        if not result.success:
            message = f"{endpoint}: {result.error}"
            warning = ProviderWarning(
                code="live_fetch_error",
                message=message,
                severity="critical",
                details={"endpoint": endpoint},
            )
            self.last_health = _build_health(
                provider="akshare",
                provider_version=self.provider_version,
                started_at=started_at,
                endpoints=(endpoint_trace,),
                warnings=(warning,),
            )
            raise ProviderUnavailable(
                f"AKShare industry catalog fetch failed: {message}"
            )
        if mapping is None or not mapping.entities:
            mapping_warnings = mapping.warnings if mapping is not None else ()
            warning = ProviderWarning(
                code="empty_live_response",
                message="AKShare returned no valid industry rows.",
                severity="critical",
                details={"endpoint": endpoint},
            )
            self.last_health = _build_health(
                provider="akshare",
                provider_version=self.provider_version,
                started_at=started_at,
                live_row_count=mapping.live_row_count if mapping else 0,
                skipped_row_count=mapping.skipped_row_count if mapping else 0,
                endpoints=(endpoint_trace,),
                warnings=(*mapping_warnings, warning),
            )
            raise ProviderUnavailable(
                "AKShare returned no valid industry rows."
            )

        updated_at = _utc_now()
        expires_at = updated_at + timedelta(days=self.cache_ttl_days)
        entities = [
            replace(
                entity,
                updated_at=updated_at.isoformat(),
                metadata={
                    **entity.metadata,
                    "provider": "akshare",
                    "as_of": resolved_as_of,
                    "updated_at": updated_at.isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "stale": False,
                },
            )
            for entity in mapping.entities
        ]
        cache_write_count = 0
        if self.cache is not None:
            self.cache.upsert_market_entities(
                entities,
                as_of=resolved_as_of,
                ttl_days=self.cache_ttl_days,
                now=updated_at,
            )
            cache_write_count = len(entities)
        self.last_health = _build_health(
            provider="akshare",
            provider_version=self.provider_version,
            started_at=started_at,
            live_row_count=mapping.live_row_count,
            mapped_row_count=len(entities),
            skipped_row_count=mapping.skipped_row_count,
            cache_write_count=cache_write_count,
            endpoints=(endpoint_trace,),
            warnings=mapping.warnings,
        )
        return entities

    def fetch_industry_history(
        self,
        symbol: str,
        *,
        name: str,
        start_date: str | None = None,
        end_date: str | None = None,
        as_of: str | None = None,
    ) -> list[MarketSeriesPoint]:
        started_at = _utc_now()
        resolved_symbol = str(symbol).strip()
        resolved_as_of = as_of or date.today().isoformat()
        if self._ak is None:
            reason = "AKShare is not installed"
            self.last_health = _build_health(
                provider="akshare",
                provider_version=self.provider_version,
                started_at=started_at,
                warnings=(
                    ProviderWarning(
                        code="live_fetch_error",
                        message=reason,
                        severity="critical",
                    ),
                ),
            )
            raise ProviderUnavailable(reason)

        range_start = (start_date or "19700101").replace("-", "")
        range_end = (end_date or resolved_as_of).replace("-", "")
        primary_endpoint = "stock_board_industry_hist_em"
        primary_result = self._call_akshare(
            primary_endpoint,
            symbol=resolved_symbol,
            start_date=range_start,
            end_date=range_end,
            period="日k",
            adjust="",
        )
        primary_mapping = (
            _industry_points_from_akshare_rows(
                primary_result.data,
                symbol=resolved_symbol,
                name=name,
                endpoint=primary_endpoint,
            )
            if primary_result.success
            else None
        )
        endpoint_traces = [
            _industry_endpoint_trace(primary_result.trace, primary_mapping)
        ]
        live_row_count = primary_mapping.live_row_count if primary_mapping else 0
        skipped_row_count = (
            primary_mapping.skipped_row_count if primary_mapping else 0
        )
        warnings = list(primary_mapping.warnings if primary_mapping else ())
        selected_endpoint = primary_endpoint
        selected_points = _filter_market_series_points(
            primary_mapping.points if primary_mapping else (),
            range_start=range_start,
            range_end=range_end,
        )

        if not primary_result.success or not selected_points:
            primary_reason = (
                primary_result.error
                if not primary_result.success
                else "no valid rows returned"
            )
            fallback_endpoint = "stock_board_industry_index_ths"
            fallback_warning = ProviderWarning(
                code="endpoint_fallback",
                message=(
                    "stock_board_industry_hist_em was unavailable; "
                    "stock_board_industry_index_ths was used."
                ),
                severity="warning",
                details={
                    "primary_endpoint": primary_endpoint,
                    "fallback_endpoint": fallback_endpoint,
                    "reason": primary_reason,
                },
            )
            fallback_result = self._call_akshare(
                fallback_endpoint,
                symbol=name,
                start_date=range_start,
                end_date=range_end,
            )
            fallback_mapping = (
                _industry_points_from_akshare_rows(
                    fallback_result.data,
                    symbol=resolved_symbol,
                    name=name,
                    endpoint=fallback_endpoint,
                )
                if fallback_result.success
                else None
            )
            endpoint_traces.append(
                _industry_endpoint_trace(fallback_result.trace, fallback_mapping)
            )
            live_row_count += (
                fallback_mapping.live_row_count if fallback_mapping else 0
            )
            skipped_row_count += (
                fallback_mapping.skipped_row_count if fallback_mapping else 0
            )
            warnings.extend(fallback_mapping.warnings if fallback_mapping else ())
            fallback_points = _filter_market_series_points(
                fallback_mapping.points if fallback_mapping else (),
                range_start=range_start,
                range_end=range_end,
            )
            if fallback_result.success and fallback_points:
                selected_endpoint = fallback_endpoint
                selected_points = fallback_points
                # A usable exact-name fallback is a degraded endpoint path, not
                # a terminal provider failure. Keep the primary endpoint trace,
                # but do not let its mapping-only critical warning degrade the
                # consumer-facing provider health.
                warnings = [
                    warning
                    for warning in warnings
                    if warning.severity != "critical"
                ]
                warnings.append(fallback_warning)
            else:
                fallback_reason = (
                    fallback_result.error
                    if not fallback_result.success
                    else "no valid rows returned"
                )
                message = (
                    f"AKShare returned no valid industry history for {resolved_symbol}: "
                    f"{primary_endpoint}={primary_reason}; "
                    f"{fallback_endpoint}={fallback_reason}"
                )
                warning = ProviderWarning(
                    code="live_fetch_error",
                    message=message,
                    severity="critical",
                    details={
                        "primary_endpoint": primary_endpoint,
                        "fallback_endpoint": fallback_endpoint,
                    },
                )
                self.last_health = _build_health(
                    provider="akshare",
                    provider_version=self.provider_version,
                    started_at=started_at,
                    live_row_count=live_row_count,
                    skipped_row_count=skipped_row_count,
                    endpoints=tuple(endpoint_traces),
                    warnings=(*warnings, warning),
                )
                raise ProviderUnavailable(message)

        if not selected_points:
            warning = ProviderWarning(
                code="empty_live_response",
                message=(
                    f"AKShare returned no valid industry history for "
                    f"{resolved_symbol}."
                ),
                severity="critical",
                details={"endpoint": endpoint, "symbol": resolved_symbol},
            )
            self.last_health = _build_health(
                provider="akshare",
                provider_version=self.provider_version,
                started_at=started_at,
                live_row_count=live_row_count,
                skipped_row_count=skipped_row_count,
                endpoints=tuple(endpoint_traces),
                warnings=(*warnings, warning),
            )
            raise ProviderUnavailable(warning.message)

        updated_at = _utc_now()
        expires_at = updated_at + timedelta(days=self.cache_ttl_days)
        normalized_points = [
            replace(
                point,
                updated_at=updated_at.isoformat(),
                metadata={
                    **point.metadata,
                    "provider": "akshare",
                    "endpoint": selected_endpoint,
                    "series_kind": "market_industry_history",
                    "as_of": resolved_as_of,
                    "updated_at": updated_at.isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "stale": False,
                },
            )
            for point in selected_points
        ]
        cache_write_count = 0
        if self.cache is not None:
            self.cache.upsert_market_series(
                normalized_points,
                as_of=resolved_as_of,
                ttl_days=self.cache_ttl_days,
                now=updated_at,
            )
            cache_write_count = len(normalized_points)
        self.last_health = _build_health(
            provider="akshare",
            provider_version=self.provider_version,
            started_at=started_at,
            live_row_count=live_row_count,
            mapped_row_count=len(normalized_points),
            skipped_row_count=skipped_row_count,
            cache_write_count=cache_write_count,
            endpoints=tuple(endpoint_traces),
            warnings=tuple(warnings),
        )
        return normalized_points

    def _fallback_to_cache(
        self,
        reason: str,
        *,
        as_of: str | None = None,
        started_at: datetime | None = None,
        live_row_count: int = 0,
        skipped_row_count: int = 0,
        warnings: tuple[ProviderWarning, ...] = (),
        endpoints: tuple[ProviderEndpointTrace, ...] = (),
    ) -> list[FundRecord]:
        started_at = started_at or _utc_now()
        if self.cache is None:
            self.last_health = _build_health(
                provider="akshare",
                provider_version=self.provider_version,
                started_at=started_at,
                live_row_count=live_row_count,
                skipped_row_count=skipped_row_count,
                fallback_used=True,
                fallback_reason=reason,
                fallback_source=None,
                endpoints=endpoints,
                warnings=(
                    *warnings,
                    ProviderWarning(code="live_fallback", message=reason, severity="critical"),
                ),
            )
            raise ProviderUnavailable(
                f"AKShareProvider unavailable and no cache fallback is configured: {reason}"
            )
        funds = self.cache.load_funds(as_of=as_of, allow_stale=self.allow_stale_cache)
        if not funds and as_of is not None:
            funds = self.cache.load_funds(allow_stale=self.allow_stale_cache)
        if not funds:
            self.last_health = _build_health(
                provider="akshare",
                provider_version=self.provider_version,
                started_at=started_at,
                live_row_count=live_row_count,
                skipped_row_count=skipped_row_count,
                fallback_used=True,
                fallback_reason=reason,
                fallback_source="cache",
                endpoints=endpoints,
                warnings=(
                    *warnings,
                    ProviderWarning(code="empty_live_response", message=reason, severity="critical"),
                ),
            )
            raise ProviderUnavailable(f"AKShareProvider unavailable and cache is empty: {reason}")
        stale_funds = [fund for fund in funds if fund.metadata.get("stale")]
        fallback_warning = ProviderWarning(
            code="live_fallback",
            message=f"AKShare live failed; using cache. reason={reason}",
            severity="warning",
        )
        stale_warning = ()
        if stale_funds:
            stale_warning = (
                ProviderWarning(
                    code="stale_cache",
                    message=f"Cache fallback used {len(stale_funds)} stale records.",
                    severity="critical",
                ),
            )
        self.last_health = _build_health(
            provider="akshare",
            provider_version=self.provider_version,
            started_at=started_at,
            live_row_count=live_row_count,
            mapped_row_count=len(funds),
            skipped_row_count=skipped_row_count,
            fallback_used=True,
            fallback_reason=reason,
            fallback_source="cache",
            endpoints=endpoints,
            warnings=(*warnings, fallback_warning, *stale_warning),
        )
        return [
            replace(
                fund,
                metadata={
                    **fund.metadata,
                    "fallback_reason": reason,
                    "fallback_provider": "akshare",
                },
            )
            for fund in funds
        ]

    def _call_akshare(self, name: str, **kwargs):
        started_at = _utc_now()
        method = getattr(self._ak, name, None)
        if not callable(method):
            error = f"AKShare endpoint is unavailable: {name}"
            return _EndpointCallResult(
                data=None,
                success=False,
                error=error,
                trace=_build_endpoint_trace(
                    endpoint=name,
                    started_at=started_at,
                    attempts=0,
                    success=False,
                    error=error,
                    timeout_seconds=self.timeout_seconds,
                ),
            )
        attempts = 0
        last_error: str | None = None
        for attempt in range(self.retry_count + 1):
            attempts = attempt + 1
            try:
                data = _call_with_timeout(
                    method,
                    timeout_seconds=self.timeout_seconds,
                    verbose=self.verbose,
                    **kwargs,
                )
            except Exception as exc:
                last_error = str(exc)
                if attempt < self.retry_count and self.retry_backoff_seconds > 0:
                    time.sleep(self.retry_backoff_seconds)
                continue
            return _EndpointCallResult(
                data=data,
                success=True,
                error=None,
                trace=_build_endpoint_trace(
                    endpoint=name,
                    started_at=started_at,
                    attempts=attempts,
                    success=True,
                    error=None,
                    timeout_seconds=self.timeout_seconds,
                ),
            )
        return _EndpointCallResult(
            data=None,
            success=False,
            error=last_error or "unknown provider error",
            trace=_build_endpoint_trace(
                endpoint=name,
                started_at=started_at,
                attempts=attempts,
                success=False,
                error=last_error or "unknown provider error",
                timeout_seconds=self.timeout_seconds,
            ),
        )


class EastmoneyProvider:
    def fetch_funds(self, *, as_of: str | None = None) -> list[FundRecord]:
        raise ProviderUnavailable("EastmoneyProvider is reserved for a later data source.")


class TiantianFundProvider:
    def __init__(
        self,
        *,
        client=None,
        cache: FundCache | None = None,
        cache_ttl_days: int = 30,
        provider_version: str | None = None,
        timeout_seconds: float = 20.0,
        retry_count: int = 0,
        retry_backoff_seconds: float = 0.0,
    ):
        self.client = client or _tiantian_client_from_env(
            timeout_seconds=timeout_seconds,
            retry_count=retry_count,
            retry_backoff_seconds=retry_backoff_seconds,
        )
        self.cache = cache
        self.cache_ttl_days = cache_ttl_days
        self._provider_version = provider_version
        self.last_health: ProviderHealth | None = None

    @property
    def available(self) -> bool:
        return self.client is not None

    @property
    def provider_version(self) -> str | None:
        if self._provider_version is not None:
            return self._provider_version
        if self.client is None:
            return None
        return getattr(self.client, "__version__", None)

    def fetch_funds(self, *, as_of: str | None = None) -> list[FundRecord]:
        raise ProviderUnavailable("TiantianFundProvider does not provide fund ranking in Phase 2C.")

    def fetch_fund_detail(self, code: str, *, as_of: str | None = None) -> FundDetail:
        started_at = _utc_now()
        resolved_code = normalize_fund_code(code)
        resolved_as_of = as_of or date.today().isoformat()
        if self.client is None:
            self.last_health = _build_health(
                provider="tiantian",
                provider_version=self.provider_version,
                started_at=started_at,
                fallback_used=True,
                fallback_reason="TiantianFundProvider client is not configured",
                warnings=(
                    ProviderWarning(
                        code="config_missing",
                        message="TiantianFundProvider client is not configured",
                        severity="critical",
                    ),
                ),
            )
            raise ProviderUnavailable("TiantianFundProvider client is not configured.")
        endpoint_started = _utc_now()
        try:
            payload = self.client.fund_detail(resolved_code)
        except Exception as exc:
            code, message = _tiantian_error_info(exc)
            endpoints = _client_endpoint_traces(
                self.client,
                fallback_endpoint="tiantian_fund_detail",
                started_at=endpoint_started,
                error=str(exc),
            )
            self.last_health = _build_health(
                provider="tiantian",
                provider_version=self.provider_version,
                started_at=started_at,
                fallback_used=True,
                fallback_reason=f"{code}: {message}",
                endpoints=endpoints,
                warnings=(ProviderWarning(code=code, message=message, severity="critical"),),
            )
            raise ProviderUnavailable(f"TiantianFundProvider detail fetch failed: {code}: {message}") from exc
        detail = _fund_detail_from_tiantian(payload, code=resolved_code, as_of=resolved_as_of)
        quality_warnings = _fund_detail_quality_warnings(payload)
        updated_at = _utc_now()
        expires_at = updated_at + timedelta(days=self.cache_ttl_days)
        detail = replace(
            detail,
            updated_at=updated_at.isoformat(),
            metadata={
                **detail.metadata,
                "provider": "tiantian",
                "as_of": resolved_as_of,
                "updated_at": updated_at.isoformat(),
                "expires_at": expires_at.isoformat(),
                "stale": False,
            },
        )
        cache_write_count = 0
        if self.cache is not None:
            self.cache.upsert_fund_details([detail], as_of=resolved_as_of, ttl_days=self.cache_ttl_days, now=updated_at)
            cache_write_count = 1
        endpoints = _client_endpoint_traces(
            self.client,
            fallback_endpoint="tiantian_fund_detail",
            started_at=endpoint_started,
            live_row_count=1,
            mapped_row_count=1,
        )
        self.last_health = _build_health(
            provider="tiantian",
            provider_version=self.provider_version,
            started_at=started_at,
            live_row_count=1,
            mapped_row_count=1,
            cache_write_count=cache_write_count,
            endpoints=endpoints,
            warnings=tuple(quality_warnings),
        )
        return detail

    def fetch_nav_history(
        self,
        code: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        as_of: str | None = None,
    ) -> list[FundNavPoint]:
        started_at = _utc_now()
        resolved_code = normalize_fund_code(code)
        resolved_as_of = as_of or date.today().isoformat()
        if self.client is None:
            self.last_health = _build_health(
                provider="tiantian",
                provider_version=self.provider_version,
                started_at=started_at,
                fallback_used=True,
                fallback_reason="TiantianFundProvider client is not configured",
                warnings=(
                    ProviderWarning(
                        code="config_missing",
                        message="TiantianFundProvider client is not configured",
                        severity="critical",
                    ),
                ),
            )
            raise ProviderUnavailable("TiantianFundProvider client is not configured.")
        endpoint_started = _utc_now()
        try:
            payload = self.client.nav_history(resolved_code, start_date=start_date, end_date=end_date)
        except Exception as exc:
            code, message = _tiantian_error_info(exc)
            endpoints = _client_endpoint_traces(
                self.client,
                fallback_endpoint="tiantian_nav_history",
                started_at=endpoint_started,
                error=str(exc),
            )
            self.last_health = _build_health(
                provider="tiantian",
                provider_version=self.provider_version,
                started_at=started_at,
                fallback_used=True,
                fallback_reason=f"{code}: {message}",
                endpoints=endpoints,
                warnings=(ProviderWarning(code=code, message=message, severity="critical"),),
            )
            raise ProviderUnavailable(f"TiantianFundProvider nav fetch failed: {code}: {message}") from exc
        nav_points, skipped_count, warnings = _nav_points_from_tiantian(payload, code=resolved_code)
        updated_at = _utc_now()
        expires_at = updated_at + timedelta(days=self.cache_ttl_days)
        nav_points = [
            replace(
                point,
                updated_at=updated_at.isoformat(),
                metadata={
                    **point.metadata,
                    "provider": "tiantian",
                    "as_of": resolved_as_of,
                    "updated_at": updated_at.isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "stale": False,
                },
            )
            for point in nav_points
        ]
        cache_write_count = 0
        if self.cache is not None and nav_points:
            self.cache.upsert_nav_points(nav_points, as_of=resolved_as_of, ttl_days=self.cache_ttl_days, now=updated_at)
            cache_write_count = len(nav_points)
        endpoints = _client_endpoint_traces(
            self.client,
            fallback_endpoint="tiantian_nav_history",
            started_at=endpoint_started,
            live_row_count=len(payload or []),
            mapped_row_count=len(nav_points),
            skipped_row_count=skipped_count,
        )
        self.last_health = _build_health(
            provider="tiantian",
            provider_version=self.provider_version,
            started_at=started_at,
            live_row_count=len(payload or []),
            mapped_row_count=len(nav_points),
            skipped_row_count=skipped_count,
            cache_write_count=cache_write_count,
            endpoints=endpoints,
            warnings=tuple(warnings),
        )
        return nav_points


@dataclass(frozen=True)
class _RowMappingResult:
    live_row_count: int
    funds: tuple[FundRecord, ...]
    skipped_row_count: int
    warnings: tuple[ProviderWarning, ...]


@dataclass(frozen=True)
class _NavMappingResult:
    live_row_count: int
    nav_points: tuple[FundNavPoint, ...]
    skipped_row_count: int
    warnings: tuple[ProviderWarning, ...]


@dataclass(frozen=True)
class _MarketSeriesMappingResult:
    live_row_count: int
    points: tuple[MarketSeriesPoint, ...]
    skipped_row_count: int
    warnings: tuple[ProviderWarning, ...]


@dataclass(frozen=True)
class _MarketEntityMappingResult:
    live_row_count: int
    entities: tuple[MarketEntity, ...]
    skipped_row_count: int
    warnings: tuple[ProviderWarning, ...]


@dataclass(frozen=True)
class _FundFeeMappingResult:
    live_row_count: int
    fees: tuple[FundFee, ...]
    skipped_row_count: int
    warnings: tuple[ProviderWarning, ...]


@dataclass(frozen=True)
class _FundCatalogMappingResult:
    live_row_count: int
    entries: tuple[FundCatalogEntry, ...]
    skipped_row_count: int
    warnings: tuple[ProviderWarning, ...]


@dataclass(frozen=True)
class _TradingRuleMappingResult:
    live_row_count: int
    rules: tuple[FundTradingRule, ...]
    skipped_row_count: int
    warnings: tuple[ProviderWarning, ...]


@dataclass(frozen=True)
class _EndpointCallResult:
    data: object | None
    success: bool
    error: str | None
    trace: ProviderEndpointTrace


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        text = str(value).replace("%", "").replace(",", "").strip()
        if not text or text == "--" or text.lower() == "nan":
            return None
        return float(text)
    except ValueError:
        return None


def _to_int(value: object) -> int | None:
    number = _to_float(value)
    return int(number) if number is not None else None


def _first(row: object, *keys: str) -> object:
    for key in keys:
        if hasattr(row, "get"):
            value = row.get(key)
        else:
            value = None
        if value is not None and str(value).strip() != "":
            return value
    return None


def _date_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text[:10] or None


def _utc_now(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _build_health(
    *,
    provider: str,
    provider_version: str | None,
    started_at: datetime,
    live_row_count: int = 0,
    mapped_row_count: int = 0,
    skipped_row_count: int = 0,
    cache_write_count: int = 0,
    fallback_used: bool = False,
    fallback_reason: str | None = None,
    fallback_source: str | None = None,
    endpoints: tuple[ProviderEndpointTrace, ...] = (),
    warnings: tuple[ProviderWarning, ...] = (),
) -> ProviderHealth:
    finished_at = _utc_now()
    return ProviderHealth(
        provider=provider,
        provider_version=provider_version,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
        duration_ms=max(0, int((finished_at - started_at).total_seconds() * 1000)),
        live_row_count=live_row_count,
        mapped_row_count=mapped_row_count,
        skipped_row_count=skipped_row_count,
        cache_write_count=cache_write_count,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        fallback_source=fallback_source,
        endpoints=endpoints,
        warnings=warnings,
    )


def _build_endpoint_trace(
    *,
    endpoint: str,
    started_at: datetime,
    attempts: int,
    success: bool,
    error: str | None,
    timeout_seconds: float | None,
) -> ProviderEndpointTrace:
    finished_at = _utc_now()
    return ProviderEndpointTrace(
        endpoint=endpoint,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
        duration_ms=max(0, int((finished_at - started_at).total_seconds() * 1000)),
        attempts=attempts,
        success=success,
        error=error,
        timeout_seconds=timeout_seconds,
    )


def _call_with_timeout(method, *, timeout_seconds: float, verbose: bool, **kwargs):
    def call():
        if verbose:
            return method(**kwargs)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return method(**kwargs)

    if (
        hasattr(signal, "SIGALRM")
        and hasattr(signal, "setitimer")
        and threading.current_thread() is threading.main_thread()
    ):
        previous_handler = signal.getsignal(signal.SIGALRM)
        previous_timer = signal.getitimer(signal.ITIMER_REAL)
        started = time.monotonic()

        def timeout_handler(_signum, _frame):
            raise ProviderCallTimeout(
                f"provider call timed out after {timeout_seconds:g} seconds"
            )

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
        try:
            return call()
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)
            previous_delay, previous_interval = previous_timer
            if previous_delay > 0:
                elapsed = time.monotonic() - started
                signal.setitimer(
                    signal.ITIMER_REAL,
                    max(previous_delay - elapsed, 0.000001),
                    previous_interval,
                )

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(call)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError as exc:
            raise ProviderCallTimeout(
                f"provider call timed out after {timeout_seconds:g} seconds"
            ) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _funds_from_rows(df: object, mapper, *, endpoint: str) -> _RowMappingResult:
    funds: list[FundRecord] = []
    warnings: list[ProviderWarning] = []
    live_row_count = 0
    skipped_row_count = 0
    for row_index, row in df.iterrows():
        live_row_count += 1
        try:
            fund = mapper(row)
        except Exception as exc:
            skipped_row_count += 1
            warnings.append(
                ProviderWarning(
                    code="skipped_rows",
                    message=f"{endpoint} row {row_index} skipped: {exc}",
                    severity="warning",
                    details={"endpoint": endpoint, "row_index": row_index},
                )
            )
            continue
        if not fund.code or not fund.name:
            skipped_row_count += 1
            warnings.append(
                ProviderWarning(
                    code="skipped_rows",
                    message=f"{endpoint} row {row_index} skipped: missing code or name",
                    severity="info",
                    details={"endpoint": endpoint, "row_index": row_index},
                )
            )
            continue
        funds.append(fund)
    return _RowMappingResult(
        live_row_count=live_row_count,
        funds=tuple(funds),
        skipped_row_count=skipped_row_count,
        warnings=tuple(warnings),
    )


def _fund_catalog_entries_from_rows(
    df: object,
    mapper,
    *,
    endpoint: str,
) -> _FundCatalogMappingResult:
    iterrows = getattr(df, "iterrows", None)
    if not callable(iterrows):
        return _FundCatalogMappingResult(
            live_row_count=0,
            entries=(),
            skipped_row_count=0,
            warnings=(
                ProviderWarning(
                    code="invalid_response",
                    message=f"{endpoint} returned a non-tabular response",
                    severity="critical",
                    details={"endpoint": endpoint},
                ),
            ),
        )
    entries: list[FundCatalogEntry] = []
    warnings: list[ProviderWarning] = []
    live_row_count = 0
    skipped_row_count = 0
    for row_index, row in iterrows():
        live_row_count += 1
        try:
            entry = mapper(row)
        except Exception as exc:
            skipped_row_count += 1
            warnings.append(
                ProviderWarning(
                    code="skipped_rows",
                    message=f"{endpoint} row {row_index} skipped: {exc}",
                    details={"endpoint": endpoint, "row_index": row_index},
                )
            )
            continue
        if len(entry.code) != 6 or not entry.code.isdigit() or not entry.name:
            skipped_row_count += 1
            warnings.append(
                ProviderWarning(
                    code="skipped_rows",
                    message=f"{endpoint} row {row_index} skipped: missing code or name",
                    severity="info",
                    details={"endpoint": endpoint, "row_index": row_index},
                )
            )
            continue
        entries.append(entry)
    return _FundCatalogMappingResult(
        live_row_count=live_row_count,
        entries=tuple(entries),
        skipped_row_count=skipped_row_count,
        warnings=tuple(warnings),
    )


def _purchase_rules_from_rows(
    df: object,
    *,
    endpoint: str,
) -> _TradingRuleMappingResult:
    iterrows = getattr(df, "iterrows", None)
    if not callable(iterrows):
        return _TradingRuleMappingResult(
            live_row_count=0,
            rules=(),
            skipped_row_count=0,
            warnings=(
                ProviderWarning(
                    code="invalid_response",
                    message=f"{endpoint} returned a non-tabular response",
                    severity="critical",
                    details={"endpoint": endpoint},
                ),
            ),
        )
    rules: list[FundTradingRule] = []
    warnings: list[ProviderWarning] = []
    live_row_count = 0
    skipped_row_count = 0
    for row_index, row in iterrows():
        live_row_count += 1
        try:
            code = normalize_fund_code(_first(row, "基金代码", "代码", "fund_code"))
            if len(code) != 6 or not code.isdigit():
                raise ValueError("missing six-digit fund code")
            rule = FundTradingRule(
                code=code,
                purchase_status=_clean_profile_text(
                    _first(row, "申购状态", "购买状态", "purchase_status")
                ),
                redemption_status=_clean_profile_text(
                    _first(row, "赎回状态", "redemption_status")
                ),
                next_open_date=_date_text(
                    _first(row, "下一开放日", "next_open_date")
                ),
                minimum_purchase_amount=_clean_profile_text(
                    _first(row, "购买起点", "起购金额", "minimum_purchase_amount")
                ),
                daily_purchase_limit=_clean_profile_text(
                    _first(row, "日累计限定金额", "日累计申购限额", "daily_purchase_limit")
                ),
                source="akshare",
                metadata={
                    "endpoint": endpoint,
                    "name": _clean_profile_text(_first(row, "基金简称", "基金名称")),
                    "fund_type": _clean_profile_text(_first(row, "基金类型")),
                    "fee_text": _clean_profile_text(_first(row, "手续费")),
                },
            )
        except Exception as exc:
            skipped_row_count += 1
            warnings.append(
                ProviderWarning(
                    code="skipped_rows",
                    message=f"{endpoint} row {row_index} skipped: {exc}",
                    details={"endpoint": endpoint, "row_index": row_index},
                )
            )
            continue
        rules.append(rule)
    return _TradingRuleMappingResult(
        live_row_count=live_row_count,
        rules=tuple(rules),
        skipped_row_count=skipped_row_count,
        warnings=tuple(warnings),
    )


def _merge_trading_rule_rows(
    df: object,
    values: dict[str, str | None],
    *,
    indicator: str,
) -> tuple[int, int, int, tuple[ProviderWarning, ...]]:
    iterrows = getattr(df, "iterrows", None)
    if not callable(iterrows):
        return (
            0,
            0,
            0,
            (
                ProviderWarning(
                    code="invalid_response",
                    message=f"fund_fee_em[{indicator}] returned a non-tabular response",
                    severity="critical",
                    details={"endpoint": "fund_fee_em", "indicator": indicator},
                ),
            ),
        )
    live_row_count = 0
    mapped_row_count = 0
    skipped_row_count = 0
    warnings: list[ProviderWarning] = []
    for row_index, row in iterrows():
        live_row_count += 1
        try:
            candidates = {
                "purchase_status": _clean_profile_text(
                    _first(row, "申购状态", "购买状态", "purchase_status")
                ),
                "redemption_status": _clean_profile_text(
                    _first(row, "赎回状态", "redemption_status")
                ),
                "next_open_date": _date_text(
                    _first(row, "下一开放日", "next_open_date")
                ),
                "minimum_purchase_amount": _clean_profile_text(
                    _first(row, "购买起点", "申购起点", "起购金额", "minimum_purchase_amount")
                ),
                "daily_purchase_limit": _clean_profile_text(
                    _first(row, "日累计限定金额", "日累计申购限额", "daily_purchase_limit")
                ),
                "confirmation_rule": _clean_profile_text(
                    _first(row, "确认规则", "交易确认日", "确认时间", "confirmation_rule")
                ),
            }
            if indicator == "交易确认日" and candidates["confirmation_rule"] is None:
                transaction_type = _clean_profile_text(
                    _first(row, "交易类型", "业务类型", "类型")
                )
                confirmation_day = _clean_profile_text(
                    _first(row, "确认日", "确认天数", "时间")
                )
                if transaction_type and confirmation_day:
                    candidates["confirmation_rule"] = f"{transaction_type} {confirmation_day}"
        except Exception as exc:
            skipped_row_count += 1
            warnings.append(
                ProviderWarning(
                    code="skipped_rows",
                    message=f"fund_fee_em[{indicator}] row {row_index} skipped: {exc}",
                    details={
                        "endpoint": "fund_fee_em",
                        "indicator": indicator,
                        "row_index": row_index,
                    },
                )
            )
            continue
        contributed = False
        for key, candidate in candidates.items():
            if candidate is None:
                continue
            if key == "confirmation_rule" and values[key] and candidate not in values[key]:
                values[key] = f"{values[key]}；{candidate}"
            elif values[key] is None:
                values[key] = candidate
            contributed = True
        if contributed:
            mapped_row_count += 1
        else:
            skipped_row_count += 1
            warnings.append(
                ProviderWarning(
                    code="skipped_rows",
                    message=f"fund_fee_em[{indicator}] row {row_index} skipped: no recognized fields",
                    severity="info",
                    details={
                        "endpoint": "fund_fee_em",
                        "indicator": indicator,
                        "row_index": row_index,
                    },
                )
            )
    return live_row_count, mapped_row_count, skipped_row_count, tuple(warnings)


def _nav_points_from_akshare_rows(
    df: object,
    *,
    code: str,
    endpoint: str,
) -> _NavMappingResult:
    nav_points: list[FundNavPoint] = []
    warnings: list[ProviderWarning] = []
    live_row_count = 0
    skipped_row_count = 0
    iterrows = getattr(df, "iterrows", None)
    if not callable(iterrows):
        return _NavMappingResult(
            live_row_count=0,
            nav_points=(),
            skipped_row_count=0,
            warnings=(
                ProviderWarning(
                    code="invalid_response",
                    message=f"{endpoint} returned a non-tabular response.",
                    severity="critical",
                    details={"endpoint": endpoint},
                ),
            ),
        )
    for row_index, row in iterrows():
        live_row_count += 1
        try:
            nav_date = _date_text(_first(row, "净值日期", "日期", "nav_date"))
            unit_nav = _to_float(_first(row, "单位净值", "最新净值", "nav"))
            accumulated_nav = _to_float(
                _first(row, "累计净值", "accumulated_nav")
            )
            daily_return = _to_float(
                _first(row, "日增长率", "日涨跌幅", "daily_return")
            )
        except Exception as exc:
            skipped_row_count += 1
            warnings.append(
                ProviderWarning(
                    code="skipped_rows",
                    message=f"{endpoint} row {row_index} skipped: {exc}",
                    severity="warning",
                    details={"endpoint": endpoint, "row_index": row_index},
                )
            )
            continue
        if not nav_date or unit_nav is None:
            skipped_row_count += 1
            warnings.append(
                ProviderWarning(
                    code="skipped_rows",
                    message=(
                        f"{endpoint} row {row_index} skipped: "
                        "missing NAV date or unit NAV"
                    ),
                    severity="info",
                    details={"endpoint": endpoint, "row_index": row_index},
                )
            )
            continue
        nav_points.append(
            FundNavPoint(
                code=code,
                date=nav_date,
                unit_nav=unit_nav,
                accumulated_nav=accumulated_nav,
                daily_return=daily_return,
                source="akshare",
            )
        )
    nav_points.sort(key=lambda item: item.date)
    return _NavMappingResult(
        live_row_count=live_row_count,
        nav_points=tuple(nav_points),
        skipped_row_count=skipped_row_count,
        warnings=tuple(warnings),
    )


def _index_points_from_akshare_rows(
    df: object,
    *,
    symbol: str,
    name: str,
    endpoint: str,
) -> _MarketSeriesMappingResult:
    points: list[MarketSeriesPoint] = []
    warnings: list[ProviderWarning] = []
    live_row_count = 0
    skipped_row_count = 0
    iterrows = getattr(df, "iterrows", None)
    if not callable(iterrows):
        return _MarketSeriesMappingResult(
            live_row_count=0,
            points=(),
            skipped_row_count=0,
            warnings=(
                ProviderWarning(
                    code="invalid_response",
                    message=f"{endpoint} returned a non-tabular response.",
                    severity="critical",
                    details={"endpoint": endpoint},
                ),
            ),
        )
    for row_index, row in iterrows():
        live_row_count += 1
        try:
            series_date = _date_text(_first(row, "date", "日期"))
            close = _to_float(_first(row, "close", "收盘"))
            point = MarketSeriesPoint(
                symbol=symbol,
                name=name,
                series_type="index",
                date=series_date or "",
                open=_to_float(_first(row, "open", "开盘")),
                close=close,
                high=_to_float(_first(row, "high", "最高")),
                low=_to_float(_first(row, "low", "最低")),
                volume=_to_float(_first(row, "volume", "成交量")),
                turnover=_to_float(_first(row, "amount", "成交额", "turnover")),
                change_pct=_to_float(_first(row, "change_pct", "涨跌幅")),
                source="akshare",
            )
        except Exception as exc:
            skipped_row_count += 1
            warnings.append(
                ProviderWarning(
                    code="skipped_rows",
                    message=f"{endpoint} row {row_index} skipped: {exc}",
                    severity="warning",
                    details={"endpoint": endpoint, "row_index": row_index},
                )
            )
            continue
        if not series_date or close is None:
            skipped_row_count += 1
            warnings.append(
                ProviderWarning(
                    code="skipped_rows",
                    message=(
                        f"{endpoint} row {row_index} skipped: "
                        "missing date or close"
                    ),
                    severity="info",
                    details={"endpoint": endpoint, "row_index": row_index},
                )
            )
            continue
        points.append(point)
    points.sort(key=lambda item: item.date)
    points = _derive_market_change_pct(points)
    return _MarketSeriesMappingResult(
        live_row_count=live_row_count,
        points=tuple(points),
        skipped_row_count=skipped_row_count,
        warnings=tuple(warnings),
    )


def _industry_entities_from_akshare_rows(
    df: object,
    *,
    endpoint: str,
    as_of: str,
) -> _MarketEntityMappingResult:
    entities: list[MarketEntity] = []
    warnings: list[ProviderWarning] = []
    live_row_count = 0
    skipped_row_count = 0
    iterrows = getattr(df, "iterrows", None)
    if not callable(iterrows):
        return _MarketEntityMappingResult(
            live_row_count=0,
            entities=(),
            skipped_row_count=0,
            warnings=(
                ProviderWarning(
                    code="invalid_response",
                    message=f"{endpoint} returned a non-tabular response.",
                    severity="critical",
                    details={"endpoint": endpoint},
                ),
            ),
        )
    for row_index, row in iterrows():
        live_row_count += 1
        symbol = str(_first(row, "板块代码", "代码") or "").strip()
        name = str(_first(row, "板块名称", "名称") or "").strip()
        if not symbol or not name:
            skipped_row_count += 1
            warnings.append(
                ProviderWarning(
                    code="skipped_rows",
                    message=(
                        f"{endpoint} row {row_index} skipped: "
                        "missing board code or name"
                    ),
                    severity="info",
                    details={"endpoint": endpoint, "row_index": row_index},
                )
            )
            continue
        try:
            entities.append(
                MarketEntity(
                    symbol=symbol,
                    name=name,
                    entity_type="industry",
                    latest=_to_float(_first(row, "最新价")),
                    change_pct=_to_float(_first(row, "涨跌幅")),
                    market_cap=_to_float(_first(row, "总市值")),
                    turnover_rate=_to_float(_first(row, "换手率")),
                    rise_count=_to_int(_first(row, "上涨家数")),
                    fall_count=_to_int(_first(row, "下跌家数")),
                    leader_name=(
                        str(_first(row, "领涨股票") or "").strip() or None
                    ),
                    leader_change_pct=_to_float(
                        _first(row, "领涨股票-涨跌幅")
                    ),
                    source="akshare",
                    as_of=as_of,
                    metadata={"endpoint": endpoint},
                )
            )
        except Exception as exc:
            skipped_row_count += 1
            warnings.append(
                ProviderWarning(
                    code="skipped_rows",
                    message=f"{endpoint} row {row_index} skipped: {exc}",
                    severity="warning",
                    details={"endpoint": endpoint, "row_index": row_index},
                )
            )
    return _MarketEntityMappingResult(
        live_row_count=live_row_count,
        entities=tuple(entities),
        skipped_row_count=skipped_row_count,
        warnings=tuple(warnings),
    )


def _industry_endpoint_trace(
    trace: ProviderEndpointTrace,
    mapping: _MarketSeriesMappingResult | None,
) -> ProviderEndpointTrace:
    if mapping is None:
        return trace
    return replace(
        trace,
        live_row_count=mapping.live_row_count,
        mapped_row_count=len(mapping.points),
        skipped_row_count=mapping.skipped_row_count,
    )


def _filter_market_series_points(
    points: tuple[MarketSeriesPoint, ...],
    *,
    range_start: str,
    range_end: str,
) -> list[MarketSeriesPoint]:
    return [
        point
        for point in points
        if range_start <= point.date.replace("-", "") <= range_end
    ]


def _industry_points_from_akshare_rows(
    df: object,
    *,
    symbol: str,
    name: str,
    endpoint: str,
) -> _MarketSeriesMappingResult:
    points: list[MarketSeriesPoint] = []
    warnings: list[ProviderWarning] = []
    live_row_count = 0
    skipped_row_count = 0
    iterrows = getattr(df, "iterrows", None)
    if not callable(iterrows):
        return _MarketSeriesMappingResult(
            live_row_count=0,
            points=(),
            skipped_row_count=0,
            warnings=(
                ProviderWarning(
                    code="invalid_response",
                    message=f"{endpoint} returned a non-tabular response.",
                    severity="critical",
                    details={"endpoint": endpoint},
                ),
            ),
        )
    for row_index, row in iterrows():
        live_row_count += 1
        try:
            series_date = _date_text(_first(row, "日期", "date"))
            close = _to_float(_first(row, "收盘", "收盘价", "close"))
            point = MarketSeriesPoint(
                symbol=symbol,
                name=name,
                series_type="industry",
                date=series_date or "",
                open=_to_float(_first(row, "开盘", "开盘价", "open")),
                close=close,
                high=_to_float(_first(row, "最高", "最高价", "high")),
                low=_to_float(_first(row, "最低", "最低价", "low")),
                volume=_to_float(_first(row, "成交量", "volume")),
                turnover=_to_float(_first(row, "成交额", "amount", "turnover")),
                change_pct=_to_float(_first(row, "涨跌幅", "change_pct")),
                source="akshare",
                metadata={
                    "endpoint": endpoint,
                    "turnover_rate": _to_float(_first(row, "换手率")),
                },
            )
        except Exception as exc:
            skipped_row_count += 1
            warnings.append(
                ProviderWarning(
                    code="skipped_rows",
                    message=f"{endpoint} row {row_index} skipped: {exc}",
                    severity="warning",
                    details={"endpoint": endpoint, "row_index": row_index},
                )
            )
            continue
        if not series_date or close is None:
            skipped_row_count += 1
            warnings.append(
                ProviderWarning(
                    code="skipped_rows",
                    message=(
                        f"{endpoint} row {row_index} skipped: "
                        "missing date or close"
                    ),
                    severity="info",
                    details={"endpoint": endpoint, "row_index": row_index},
                )
            )
            continue
        points.append(point)
    points.sort(key=lambda item: item.date)
    return _MarketSeriesMappingResult(
        live_row_count=live_row_count,
        points=tuple(points),
        skipped_row_count=skipped_row_count,
        warnings=tuple(warnings),
    )


def _derive_market_change_pct(
    points: list[MarketSeriesPoint],
) -> list[MarketSeriesPoint]:
    derived: list[MarketSeriesPoint] = []
    previous_close: float | None = None
    for point in points:
        change_pct = point.change_pct
        if (
            change_pct is None
            and previous_close not in {None, 0}
            and point.close is not None
        ):
            change_pct = (point.close / previous_close - 1.0) * 100.0
        derived.append(replace(point, change_pct=change_pct))
        if point.close is not None:
            previous_close = point.close
    return derived


def _dedupe_funds(funds: list[FundRecord]) -> list[FundRecord]:
    by_code: dict[str, FundRecord] = {}
    for fund in funds:
        existing = by_code.get(fund.code)
        if existing is None or fund.exchange_traded:
            by_code[fund.code] = fund
    return list(by_code.values())


def _with_provider_metadata(
    fund: FundRecord,
    *,
    as_of: str,
    provider: str,
    updated_at: datetime,
    expires_at: datetime,
) -> FundRecord:
    return replace(
        fund,
        metadata={
            **fund.metadata,
            "provider": provider,
            "as_of": as_of,
            "updated_at": updated_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "stale": False,
        },
    )


def _fund_from_akshare_row(row: object) -> FundRecord:
    return FundRecord(
        code=normalize_fund_code(_first(row, "基金代码", "代码", "fund_code")),
        name=normalize_fund_name(_first(row, "基金简称", "基金名称", "name")),
        category=normalize_fund_category(_first(row, "基金类型", "类型", "category")),
        nav=_to_float(_first(row, "单位净值", "最新净值", "nav")),
        nav_date=_date_text(_first(row, "日期", "净值日期", "nav_date")),
        valuation_date=_date_text(_first(row, "估值日期", "valuation_date")),
        returns={
            "1w": _to_float(_first(row, "近1周", "近一周")) or 0.0,
            "1m": _to_float(_first(row, "近1月", "近一月")) or 0.0,
            "3m": _to_float(_first(row, "近3月", "近三月")) or 0.0,
            "6m": _to_float(_first(row, "近6月", "近六月")) or 0.0,
            "1y": _to_float(_first(row, "近1年", "近一年")) or 0.0,
        },
        scale_billion=_to_float(_first(row, "规模", "基金规模", "scale_billion")),
        manager=normalize_fund_name(_first(row, "基金经理", "manager")) or None,
        fee_rate=_to_float(_first(row, "费率", "手续费", "fee_rate")),
        source="akshare",
    )


def _fund_catalog_from_name_row(row: object) -> FundCatalogEntry:
    return FundCatalogEntry(
        code=normalize_fund_code(_first(row, "基金代码", "代码", "fund_code")),
        name=normalize_fund_name(_first(row, "基金简称", "基金名称", "名称", "name")),
        fund_type=_clean_profile_text(_first(row, "基金类型", "类型", "fund_type")),
        exchange_traded=False,
        catalog_sources=("fund_name_em",),
        source="akshare",
        metadata={"endpoint": "fund_name_em"},
    )


def _fund_catalog_from_rank_row(row: object) -> FundCatalogEntry:
    return FundCatalogEntry(
        code=normalize_fund_code(_first(row, "基金代码", "代码", "fund_code")),
        name=normalize_fund_name(_first(row, "基金简称", "基金名称", "名称", "name")),
        fund_type=_clean_profile_text(_first(row, "基金类型", "类型", "fund_type")),
        exchange_traded=False,
        catalog_sources=("fund_open_fund_rank_em",),
        source="akshare",
        metadata={"endpoint": "fund_open_fund_rank_em"},
    )


def _fund_catalog_from_etf_row(row: object) -> FundCatalogEntry:
    return FundCatalogEntry(
        code=normalize_fund_code(_first(row, "代码", "基金代码", "fund_code")),
        name=normalize_fund_name(_first(row, "名称", "基金简称", "基金名称", "name")),
        fund_type="ETF",
        exchange_traded=True,
        catalog_sources=("fund_etf_spot_em",),
        source="akshare",
        metadata={"endpoint": "fund_etf_spot_em"},
    )


def _dedupe_catalog_entries(
    entries: list[FundCatalogEntry],
) -> list[FundCatalogEntry]:
    by_code: dict[str, FundCatalogEntry] = {}
    for entry in entries:
        existing = by_code.get(entry.code)
        if existing is None:
            by_code[entry.code] = entry
            continue
        sources = tuple(dict.fromkeys((*existing.catalog_sources, *entry.catalog_sources)))
        endpoints = tuple(
            dict.fromkeys(
                (
                    *existing.metadata.get("endpoints", (existing.metadata.get("endpoint"),)),
                    *entry.metadata.get("endpoints", (entry.metadata.get("endpoint"),)),
                )
            )
        )
        by_code[entry.code] = replace(
            existing,
            name=entry.name if entry.exchange_traded else existing.name,
            fund_type=(
                entry.fund_type
                if entry.exchange_traded or existing.fund_type is None
                else existing.fund_type
            ),
            exchange_traded=existing.exchange_traded or entry.exchange_traded,
            catalog_sources=sources,
            metadata={"endpoints": tuple(item for item in endpoints if item)},
        )
    return [by_code[code] for code in sorted(by_code)]


def _fund_profile_from_akshare_row(
    row: object,
    *,
    code: str | None = None,
) -> FundProfile:
    resolved_code = normalize_fund_code(
        code if code is not None else _first(row, "基金代码", "代码", "fund_code")
    )
    if len(resolved_code) != 6 or not resolved_code.isdigit():
        raise ValueError("profile requires a six-digit fund code")

    inception_and_scale = _clean_profile_text(
        _first(row, "成立日期/规模", "基金成立日期/规模")
    )
    inception_date = _date_text(
        _first(row, "成立日期", "基金成立日", "基金成立日期", "inception_date")
    )
    share_scale_text = _clean_profile_text(
        _first(row, "份额规模", "基金份额规模", "share_scale")
    )
    if inception_and_scale:
        combined_parts = re.split(r"\s*[/／]\s*", inception_and_scale, maxsplit=1)
        if inception_date is None:
            inception_date = _date_text(combined_parts[0])
        if share_scale_text is None and len(combined_parts) == 2:
            share_scale_text = combined_parts[1]

    asset_scale, asset_scale_unit = _scale_value_and_unit(
        _first(row, "资产规模", "基金资产规模", "asset_scale")
    )
    share_scale, share_scale_unit = _scale_value_and_unit(share_scale_text)
    full_name = _clean_profile_text(
        _first(row, "基金全称", "基金名称", "full_name")
    )
    short_name = _clean_profile_text(
        _first(row, "基金简称", "简称", "name")
    )
    if short_name is None:
        short_name = full_name

    return FundProfile(
        code=resolved_code,
        name=short_name,
        full_name=full_name,
        fund_type=_clean_profile_text(
            _first(row, "基金类型", "类型", "fund_type")
        ),
        fund_company=_clean_profile_text(
            _first(row, "基金管理人", "基金公司", "管理人", "fund_company")
        ),
        custodian=_clean_profile_text(
            _first(row, "基金托管人", "托管人", "custodian")
        ),
        fund_manager=_clean_profile_text(
            _first(row, "基金经理人", "基金经理", "经理", "fund_manager")
        ),
        issue_date=_date_text(_first(row, "发行日期", "认购日期", "issue_date")),
        inception_date=inception_date,
        asset_scale=asset_scale,
        asset_scale_unit=asset_scale_unit,
        share_scale=share_scale,
        share_scale_unit=share_scale_unit,
        benchmark=_clean_profile_text(
            _first(row, "业绩比较基准", "业绩基准", "benchmark")
        ),
        tracking_target=_clean_tracking_target(
            _first(row, "跟踪标的", "跟踪标的名称", "tracking_target")
        ),
        source="akshare",
        metadata={"endpoint": "fund_overview_em"},
    )


def _fund_fees_from_akshare_rows(
    df: object,
    *,
    code: str,
    indicator: str,
) -> _FundFeeMappingResult:
    resolved_code = normalize_fund_code(code)
    if len(resolved_code) != 6 or not resolved_code.isdigit():
        raise ValueError("fees require a six-digit fund code")
    iterrows = getattr(df, "iterrows", None)
    if not callable(iterrows):
        return _FundFeeMappingResult(
            live_row_count=0,
            fees=(),
            skipped_row_count=0,
            warnings=(
                ProviderWarning(
                    code="invalid_response",
                    message="fund_fee_em returned a non-tabular response",
                    severity="critical",
                    details={"endpoint": "fund_fee_em", "indicator": indicator},
                ),
            ),
        )

    fees: list[FundFee] = []
    warnings: list[ProviderWarning] = []
    live_row_count = 0
    skipped_row_count = 0
    for row_index, row in iterrows():
        live_row_count += 1
        try:
            condition = _clean_profile_text(
                _first(row, "适用金额", "适用条件", "金额条件", "condition")
            )
            period = _clean_profile_text(
                _first(row, "适用期限", "持有期限", "期限", "period")
            )
            original_rate = _clean_profile_text(
                _first(row, "原费率", "费率", "标准费率", "original_rate")
            )
            channels = _fee_channels(row)
        except Exception as exc:
            skipped_row_count += 1
            warnings.append(
                ProviderWarning(
                    code="skipped_rows",
                    message=f"fund_fee_em row {row_index} skipped: {exc}",
                    details={"endpoint": "fund_fee_em", "row_index": row_index},
                )
            )
            continue
        if original_rate is None and not channels:
            skipped_row_count += 1
            warnings.append(
                ProviderWarning(
                    code="skipped_rows",
                    message=f"fund_fee_em row {row_index} skipped: missing fee value",
                    severity="info",
                    details={"endpoint": "fund_fee_em", "row_index": row_index},
                )
            )
            continue
        if not channels:
            channels = ((None, None),)
        for channel, discounted_rate in channels:
            fees.append(
                FundFee(
                    code=resolved_code,
                    fee_type=str(indicator or "费率").strip() or "费率",
                    condition=condition,
                    period=period,
                    channel=channel,
                    original_rate=original_rate,
                    discounted_rate=discounted_rate,
                    source="akshare",
                    metadata={"endpoint": "fund_fee_em", "indicator": indicator},
                )
            )
    return _FundFeeMappingResult(
        live_row_count=live_row_count,
        fees=tuple(fees),
        skipped_row_count=skipped_row_count,
        warnings=tuple(warnings),
    )


def _clean_profile_text(value: object) -> str | None:
    text = str(value or "").strip()
    if not text or text in {"--", "-", "暂无", "无", "nan", "None"}:
        return None
    return text


def _clean_tracking_target(value: object) -> str | None:
    text = _clean_profile_text(value)
    if text is None or "无跟踪标的" in text:
        return None
    return text


def _scale_value_and_unit(value: object) -> tuple[float | None, str | None]:
    text = _clean_profile_text(value)
    if text is None:
        return None, None
    match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*((?:万|亿)?(?:元|份))", text)
    if match is None:
        return None, None
    return float(match.group(1)), match.group(2)


def _fee_channels(row: object) -> tuple[tuple[str | None, str | None], ...]:
    channel_columns = (
        ("天天基金优惠费率-银行卡购买", "银行卡购买"),
        ("天天基金优惠费率-活期宝购买", "活期宝购买"),
        ("天天基金优惠费率 银行卡购买", "银行卡购买"),
        ("天天基金优惠费率 活期宝购买", "活期宝购买"),
        ("天天基金优惠费率", "天天基金"),
        ("优惠费率", "优惠"),
    )
    channels: list[tuple[str | None, str | None]] = []
    seen: set[tuple[str | None, str | None]] = set()
    for column, channel in channel_columns:
        discounted_rate = _clean_profile_text(_first(row, column))
        item = (channel, discounted_rate)
        if discounted_rate is not None and item not in seen:
            channels.append(item)
            seen.add(item)
    return tuple(channels)


def _fund_from_mapping(item: dict, *, source: str) -> FundRecord:
    return FundRecord(
        code=normalize_fund_code(item["code"]),
        name=normalize_fund_name(item["name"]),
        category=normalize_fund_category(item.get("category", "基金")),
        nav=_to_float(item.get("nav")),
        nav_date=item.get("nav_date"),
        valuation_date=item.get("valuation_date"),
        returns={key: float(value) for key, value in item.get("returns", {}).items()},
        scale_billion=_to_float(item.get("scale_billion")),
        manager=item.get("manager"),
        fee_rate=_to_float(item.get("fee_rate")),
        exchange_traded=bool(item.get("exchange_traded", False)),
        price=_to_float(item.get("price")),
        target_etf=item.get("target_etf"),
        proxy_symbol=item.get("proxy_symbol"),
        source=source,
        metadata=dict(item.get("metadata", {})),
    )


def _fund_from_akshare_etf_row(row: object) -> FundRecord:
    market_value = _to_float(_first(row, "总市值", "流通市值"))
    return FundRecord(
        code=normalize_fund_code(_first(row, "代码", "基金代码", "fund_code")),
        name=normalize_fund_name(_first(row, "名称", "基金简称", "基金名称", "name")),
        category="ETF",
        nav=_to_float(_first(row, "IOPV实时估值", "单位净值", "nav")),
        nav_date=_date_text(_first(row, "数据日期", "日期", "nav_date")),
        valuation_date=_date_text(_first(row, "数据日期", "估值日期", "valuation_date")),
        returns={
            "1w": 0.0,
            "1m": 0.0,
            "3m": 0.0,
            "6m": 0.0,
            "1y": 0.0,
        },
        scale_billion=None if market_value is None else market_value / 100000000,
        exchange_traded=True,
        price=_to_float(_first(row, "最新价", "price")),
        source="akshare",
        metadata={
            "source_updated_at": str(_first(row, "更新时间", "updated_at") or ""),
            "daily_change_pct": _to_float(_first(row, "涨跌幅", "change_pct")),
            "discount_rate": _to_float(_first(row, "基金折价率", "discount_rate")),
        },
    )


def _fund_detail_from_tiantian(payload: object, *, code: str, as_of: str) -> FundDetail:
    row = payload if hasattr(payload, "get") else {}
    return FundDetail(
        code=normalize_fund_code(_first(row, "code", "基金代码", "fund_code") or code),
        name=normalize_fund_name(_first(row, "name", "基金名称", "基金简称") or code),
        fund_type=_none_if_blank(_first(row, "fund_type", "基金类型", "type")),
        fund_company=_none_if_blank(_first(row, "fund_company", "基金公司", "company")),
        fund_manager=_none_if_blank(_first(row, "fund_manager", "基金经理", "manager")),
        inception_date=_date_text(_first(row, "inception_date", "成立日期", "成立时间")),
        scale=_to_float(_first(row, "scale", "基金规模", "规模")),
        rating=_none_if_blank(_first(row, "rating", "评级", "基金评级")),
        source="tiantian",
        as_of=as_of,
        metadata={"raw_keys": sorted(str(key) for key in row.keys()) if hasattr(row, "keys") else []},
    )


def _fund_detail_quality_warnings(payload: object) -> list[ProviderWarning]:
    row = payload if hasattr(payload, "get") else {}
    checks = {
        "name": ("name", "基金名称", "基金简称"),
        "fund_company": ("fund_company", "基金公司", "company"),
        "fund_manager": ("fund_manager", "基金经理", "manager"),
        "scale": ("scale", "基金规模", "规模"),
        "rating": ("rating", "评级", "基金评级"),
        "inception_date": ("inception_date", "成立日期", "成立时间"),
    }
    warnings: list[ProviderWarning] = []
    for field, keys in checks.items():
        if _first(row, *keys) is None:
            warnings.append(
                ProviderWarning(
                    code=f"detail_missing_{field}",
                    message=f"Tiantian fund detail missing {field}.",
                    severity="warning",
                    details={"field": field, "endpoint": "tiantian_fund_detail"},
                )
            )
    return warnings


def _nav_points_from_tiantian(payload: object, *, code: str) -> tuple[list[FundNavPoint], int, list[ProviderWarning]]:
    rows = payload if isinstance(payload, list) else []
    points: list[FundNavPoint] = []
    warnings: list[ProviderWarning] = []
    skipped = 0
    for row_index, row in enumerate(rows):
        try:
            date_text = _date_text(_first(row, "date", "净值日期", "FSRQ"))
            if not date_text:
                raise ValueError("missing date")
            points.append(
                FundNavPoint(
                    code=code,
                    date=date_text,
                    unit_nav=_to_float(_first(row, "unit_nav", "单位净值", "DWJZ")),
                    accumulated_nav=_to_float(_first(row, "accumulated_nav", "累计净值", "LJJZ")),
                    daily_return=_to_float(_first(row, "daily_return", "日增长率", "JZZZL")),
                    source="tiantian",
                    metadata={"row_index": row_index},
                )
            )
        except Exception as exc:
            skipped += 1
            warnings.append(
                ProviderWarning(
                    code="skipped_rows",
                    message=f"tiantian_nav_history row {row_index} skipped: {exc}",
                    severity="warning",
                    details={"endpoint": "tiantian_nav_history", "row_index": row_index},
                )
            )
    return points, skipped, warnings


def _none_if_blank(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _tiantian_error_info(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, TiantianProviderError):
        return exc.code, str(exc).split(": ", 1)[-1]
    return "mapping_error", str(exc)


def _client_endpoint_traces(
    client,
    *,
    fallback_endpoint: str,
    started_at: datetime,
    live_row_count: int = 0,
    mapped_row_count: int = 0,
    skipped_row_count: int = 0,
    error: str | None = None,
) -> tuple[ProviderEndpointTrace, ...]:
    traces = tuple(getattr(client, "last_endpoint_traces", ()) or ())
    if traces:
        if error is None:
            return tuple(
                replace(
                    trace,
                    live_row_count=trace.live_row_count or live_row_count,
                    mapped_row_count=trace.mapped_row_count or mapped_row_count,
                    skipped_row_count=trace.skipped_row_count or skipped_row_count,
                )
                for trace in traces
            )
        return traces
    endpoint = _build_endpoint_trace(
        endpoint=fallback_endpoint,
        started_at=started_at,
        attempts=1,
        success=error is None,
        error=error,
        timeout_seconds=None,
    )
    return (
        replace(
            endpoint,
            live_row_count=live_row_count,
            mapped_row_count=mapped_row_count,
            skipped_row_count=skipped_row_count,
        ),
    )


class _TiantianHttpClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 20.0,
        retry_count: int = 0,
        retry_backoff_seconds: float = 0.0,
        page_size: int = 200,
        max_pages: int = 200,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count
        self.retry_backoff_seconds = retry_backoff_seconds
        self.page_size = page_size
        self.max_pages = max(1, max_pages)
        self.last_endpoint_traces: tuple[ProviderEndpointTrace, ...] = ()

    def fund_detail(self, code: str):
        payload = self._get_json(
            "tiantian_fund_detail",
            "/fundMNDetailInformation",
            {"FCODE": code},
        )
        data = _extract_tiantian_data(payload)
        if _is_empty_tiantian_payload(data):
            raise TiantianProviderError("empty_response", "Tiantian fund detail returned no data")
        return data

    def nav_history(self, code: str, start_date=None, end_date=None):
        rows: list[object] = []
        traces: list[ProviderEndpointTrace] = []
        page_index = 1
        total_pages: int | None = None
        while True:
            payload = self._get_json(
                "tiantian_nav_history",
                "/fundMNHisNetList",
                {"FCODE": code, "pageIndex": page_index, "pagesize": self.page_size},
            )
            page_rows = _extract_tiantian_rows(payload)
            traces.extend(
                replace(trace, live_row_count=len(page_rows))
                for trace in self.last_endpoint_traces
            )
            if not page_rows:
                if page_index == 1:
                    raise TiantianProviderError("empty_response", "Tiantian nav history returned no rows")
                break
            rows.extend(page_rows)
            total_pages = _extract_total_pages(payload) or total_pages
            if total_pages is not None and page_index >= total_pages:
                break
            if len(page_rows) < self.page_size and total_pages is None:
                break
            if page_index >= self.max_pages:
                break
            page_index += 1
        self.last_endpoint_traces = tuple(traces)
        if start_date or end_date:
            rows = [
                row
                for row in rows
                if (not start_date or str(row.get("FSRQ", "")) >= start_date)
                and (not end_date or str(row.get("FSRQ", "")) <= end_date)
            ]
        return rows

    def _get_json(self, endpoint: str, path: str, params: dict[str, object]):
        url = f"{self.base_url}{path}?{urlencode(params)}"
        started_at = _utc_now()
        attempts = 0
        last_error: TiantianProviderError | None = None
        for attempt in range(self.retry_count + 1):
            attempts = attempt + 1
            try:
                with urlopen(url, timeout=self.timeout_seconds) as response:  # nosec: user-provided base URL
                    payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, (dict, list)):
                    raise TiantianProviderError("invalid_response", "Tiantian response root is not JSON object/list")
                self.last_endpoint_traces = (
                    _build_endpoint_trace(
                        endpoint=endpoint,
                        started_at=started_at,
                        attempts=attempts,
                        success=True,
                        error=None,
                        timeout_seconds=self.timeout_seconds,
                    ),
                )
                return payload
            except Exception as exc:
                last_error = _classify_tiantian_exception(exc)
                if attempt < self.retry_count and self.retry_backoff_seconds > 0:
                    time.sleep(self.retry_backoff_seconds)
        self.last_endpoint_traces = (
            _build_endpoint_trace(
                endpoint=endpoint,
                started_at=started_at,
                attempts=attempts,
                success=False,
                error=str(last_error) if last_error else "unknown",
                timeout_seconds=self.timeout_seconds,
            ),
        )
        raise last_error or TiantianProviderError("connection_error", "unknown Tiantian provider error")


def _extract_tiantian_data(payload: object) -> object:
    if hasattr(payload, "get"):
        return payload.get("Datas", payload)
    return payload


def _extract_tiantian_rows(payload: object) -> list[object]:
    data = _extract_tiantian_data(payload)
    if isinstance(data, list):
        return data
    if hasattr(data, "get"):
        for key in ("LSJZList", "list", "rows", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def _extract_total_pages(payload: object) -> int | None:
    candidates = []
    if hasattr(payload, "get"):
        candidates.extend(
            [
                payload.get("TotalPages"),
                payload.get("totalPages"),
                payload.get("pages"),
                payload.get("total_pages"),
            ]
        )
        data = payload.get("Datas")
        if hasattr(data, "get"):
            candidates.extend(
                [
                    data.get("TotalPages"),
                    data.get("totalPages"),
                    data.get("pages"),
                    data.get("total_pages"),
                ]
            )
    for value in candidates:
        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _is_empty_tiantian_payload(data: object) -> bool:
    if data is None:
        return True
    if isinstance(data, (list, dict, str)):
        return len(data) == 0
    return False


def _classify_tiantian_exception(exc: Exception) -> TiantianProviderError:
    if isinstance(exc, TiantianProviderError):
        return exc
    if isinstance(exc, HTTPError):
        return TiantianProviderError("http_error", f"HTTP {exc.code}: {exc.reason}")
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return TiantianProviderError("timeout", str(exc) or "Tiantian request timed out")
    if isinstance(exc, URLError):
        return TiantianProviderError("connection_error", str(exc.reason))
    if isinstance(exc, json.JSONDecodeError):
        return TiantianProviderError("invalid_response", str(exc))
    return TiantianProviderError("connection_error", str(exc))


def _tiantian_client_from_env(
    *,
    timeout_seconds: float = 20.0,
    retry_count: int = 0,
    retry_backoff_seconds: float = 0.0,
):
    base_url = os.environ.get("TIANTIAN_API_BASE_URL")
    if not base_url:
        return None
    timeout = _to_float(os.environ.get("TIANTIAN_TIMEOUT_SECONDS")) or timeout_seconds
    retries = int(_to_float(os.environ.get("TIANTIAN_RETRY_COUNT")) or retry_count)
    backoff = _to_float(os.environ.get("TIANTIAN_RETRY_BACKOFF_SECONDS")) or retry_backoff_seconds
    return _TiantianHttpClient(
        base_url,
        timeout_seconds=timeout,
        retry_count=max(0, retries),
        retry_backoff_seconds=max(0.0, backoff),
    )


def load_portfolio_file(path: Path | str) -> list[PortfolioHolding]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    holdings = payload.get("holdings", payload if isinstance(payload, list) else [])
    return [
        PortfolioHolding(
            code=str(item["code"]),
            name=str(item.get("name", item["code"])),
            shares=float(item["shares"]),
            cost_nav=float(item["cost_nav"]),
            buy_date=str(item.get("buy_date", "")),
            target_weight=(
                None if item.get("target_weight") is None else float(item["target_weight"])
            ),
            notes=str(item.get("notes", "")),
        )
        for item in holdings
    ]
