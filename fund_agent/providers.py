from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .models import FundRecord
from .portfolio import PortfolioHolding


class ProviderUnavailable(RuntimeError):
    """Raised when an optional live provider is not available."""


class FundProvider(Protocol):
    def fetch_funds(self) -> list[FundRecord]:
        """Return normalized fund records."""


class FixtureProvider:
    def __init__(self, funds_path: Path | str = Path("data/fixtures/funds.json")):
        self.funds_path = Path(funds_path)

    def fetch_funds(self) -> list[FundRecord]:
        payload = json.loads(self.funds_path.read_text(encoding="utf-8"))
        return [_fund_from_mapping(item, source="fixture") for item in payload]


class AkshareProvider:
    """Optional live provider.

    The MVP keeps AKShare behind a boundary so the demo and tests never need
    network access. When AKShare is not installed, callers receive a clear
    ProviderUnavailable error instead of an import failure.
    """

    def __init__(self, fund_type: str = "全部"):
        self.fund_type = fund_type
        try:
            import akshare as ak  # type: ignore
        except Exception:  # pragma: no cover - depends on local environment
            self._ak = None
        else:  # pragma: no cover - live provider is smoke-tested manually
            self._ak = ak

    @property
    def available(self) -> bool:
        return self._ak is not None

    def fetch_funds(self) -> list[FundRecord]:
        if self._ak is None:
            raise ProviderUnavailable("AKShare is not installed; use FixtureProvider or install akshare.")
        df = self._ak.fund_open_fund_rank_em(symbol=self.fund_type)
        funds: list[FundRecord] = []
        for _, row in df.iterrows():
            funds.append(
                FundRecord(
                    code=str(row.get("基金代码", "")).strip(),
                    name=str(row.get("基金简称", "")).strip(),
                    category=str(row.get("基金类型", "开放式基金")).strip(),
                    nav=_to_float(row.get("单位净值")),
                    nav_date=str(row.get("日期", "") or "")[:10] or None,
                    returns={
                        "1w": _to_float(row.get("近1周")) or 0.0,
                        "1m": _to_float(row.get("近1月")) or 0.0,
                        "3m": _to_float(row.get("近3月")) or 0.0,
                        "6m": _to_float(row.get("近6月")) or 0.0,
                        "1y": _to_float(row.get("近1年")) or 0.0,
                    },
                    source="akshare",
                )
            )
        return [fund for fund in funds if fund.code and fund.name]


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


def _fund_from_mapping(item: dict, *, source: str) -> FundRecord:
    return FundRecord(
        code=str(item["code"]),
        name=str(item["name"]),
        category=str(item.get("category", "基金")),
        nav=_to_float(item.get("nav")),
        nav_date=item.get("nav_date"),
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
