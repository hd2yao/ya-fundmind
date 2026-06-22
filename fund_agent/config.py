from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .portfolio import PortfolioHolding
from .providers import normalize_fund_code


@dataclass(frozen=True)
class WatchlistConfig:
    name: str
    codes: tuple[str, ...]


@dataclass(frozen=True)
class PortfolioConfig:
    name: str
    cash_available: float
    holdings: tuple[PortfolioHolding, ...]


def load_watchlist_config(path: Path | str) -> WatchlistConfig:
    payload = _parse_simple_yaml(Path(path))
    funds = payload.get("funds", [])
    codes = tuple(
        normalize_fund_code(item.get("code", ""))
        for item in funds
        if isinstance(item, dict) and item.get("code") is not None
    )
    return WatchlistConfig(name=str(payload.get("name", "watchlist")), codes=codes)


def load_portfolio_config(path: Path | str) -> PortfolioConfig:
    payload = _parse_simple_yaml(Path(path))
    holdings = tuple(
        PortfolioHolding(
            code=normalize_fund_code(item["code"]),
            name=str(item.get("name", item["code"])),
            shares=float(item["shares"]),
            cost_nav=float(item["cost_nav"]),
            buy_date=str(item.get("buy_date", "")),
            target_weight=(
                None if item.get("target_weight") is None else float(item["target_weight"])
            ),
            notes=str(item.get("notes", "")),
        )
        for item in payload.get("holdings", [])
        if isinstance(item, dict)
    )
    return PortfolioConfig(
        name=str(payload.get("name", "portfolio")),
        cash_available=float(payload.get("cash_available", 0.0) or 0.0),
        holdings=holdings,
    )


def _parse_simple_yaml(path: Path) -> dict:
    payload: dict[str, object] = {}
    current_list: list[dict[str, object]] | None = None
    current_item: dict[str, object] | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if not line.startswith(" ") and stripped.endswith(":"):
            key = stripped[:-1]
            current_list = []
            payload[key] = current_list
            current_item = None
            continue
        if not line.startswith(" ") and ":" in stripped:
            key, value = _split_key_value(stripped)
            payload[key] = _parse_scalar(value)
            current_list = None
            current_item = None
            continue
        if stripped.startswith("- "):
            if current_list is None:
                raise ValueError(f"List item without list key in {path}: {raw_line}")
            current_item = {}
            current_list.append(current_item)
            rest = stripped[2:].strip()
            if rest:
                key, value = _split_key_value(rest)
                current_item[key] = _parse_scalar(value)
            continue
        if current_item is not None and ":" in stripped:
            key, value = _split_key_value(stripped)
            current_item[key] = _parse_scalar(value)
            continue
        raise ValueError(f"Unsupported YAML subset in {path}: {raw_line}")

    return payload


def _split_key_value(text: str) -> tuple[str, str]:
    key, value = text.split(":", 1)
    return key.strip(), value.strip()


def _parse_scalar(value: str) -> object:
    text = value.strip()
    if not text:
        return ""
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        return text[1:-1]
    lower = text.lower()
    if lower in {"null", "none"}:
        return None
    if lower in {"true", "false"}:
        return lower == "true"
    if text.isdigit() and len(text) > 1 and text.startswith("0"):
        return text
    if text.isdigit():
        return int(text)
    try:
        return float(text)
    except ValueError:
        return text
