from __future__ import annotations

import json
import contextlib
import io
import concurrent.futures
import os
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
from .models import FundDetail, FundNavPoint, FundRecord, ProviderEndpointTrace, ProviderHealth, ProviderWarning
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


def normalize_fund_name(value: object) -> str:
    return str(value or "").strip()


def normalize_fund_category(value: object) -> str:
    text = str(value or "").strip()
    return text or "基金"


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
        method = getattr(self._ak, name)
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
