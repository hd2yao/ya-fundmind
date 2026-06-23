from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from .cache import FundCache
from .models import FundRecord
from .portfolio import PortfolioHolding


class ProviderUnavailable(RuntimeError):
    """Raised when an optional live provider is not available."""


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

    def fetch_funds(self, *, as_of: str | None = None) -> list[FundRecord]:
        payload = json.loads(self.funds_path.read_text(encoding="utf-8"))
        return [_fund_from_mapping(item, source="fixture") for item in payload]


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
    ):
        self.fund_type = fund_type
        self.cache = cache
        self.allow_stale_cache = allow_stale_cache
        self.cache_ttl_days = cache_ttl_days
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

    def fetch_funds(self, *, as_of: str | None = None) -> list[FundRecord]:
        resolved_as_of = as_of or date.today().isoformat()
        if self._ak is None:
            return self._fallback_to_cache("AKShare is not installed", as_of=resolved_as_of)
        errors: list[str] = []
        funds: list[FundRecord] = []
        try:
            df = self._ak.fund_open_fund_rank_em(symbol=self.fund_type)
        except Exception as exc:
            errors.append(f"fund_open_fund_rank_em: {exc}")
        else:
            funds.extend(_funds_from_rows(df, _fund_from_akshare_row))
        if hasattr(self._ak, "fund_etf_spot_em"):
            try:
                etf_df = self._ak.fund_etf_spot_em()
            except Exception as exc:
                errors.append(f"fund_etf_spot_em: {exc}")
            else:
                funds.extend(_funds_from_rows(etf_df, _fund_from_akshare_etf_row))
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
            )
        if self.cache is not None and normalized_funds:
            self.cache.upsert_funds(
                normalized_funds,
                as_of=resolved_as_of,
                ttl_days=self.cache_ttl_days,
                now=updated_at,
            )
        return normalized_funds

    def _fallback_to_cache(self, reason: str, *, as_of: str | None = None) -> list[FundRecord]:
        if self.cache is None:
            raise ProviderUnavailable(
                f"AKShareProvider unavailable and no cache fallback is configured: {reason}"
            )
        funds = self.cache.load_funds(as_of=as_of, allow_stale=self.allow_stale_cache)
        if not funds and as_of is not None:
            funds = self.cache.load_funds(allow_stale=self.allow_stale_cache)
        if not funds:
            raise ProviderUnavailable(f"AKShareProvider unavailable and cache is empty: {reason}")
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


class EastmoneyProvider:
    def fetch_funds(self, *, as_of: str | None = None) -> list[FundRecord]:
        raise ProviderUnavailable("EastmoneyProvider is reserved for a later data source.")


class TiantianFundProvider:
    def fetch_funds(self, *, as_of: str | None = None) -> list[FundRecord]:
        raise ProviderUnavailable("TiantianFundProvider is reserved for a later data source.")


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


def _funds_from_rows(df: object, mapper) -> list[FundRecord]:
    funds: list[FundRecord] = []
    for _, row in df.iterrows():
        try:
            funds.append(mapper(row))
        except Exception:
            continue
    return funds


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
