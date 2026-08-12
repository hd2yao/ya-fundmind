from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cache import FundCache
from .models import FundCatalogEntry, FundTradingRule
from .providers import normalize_fund_code


RETURN_WINDOWS = ("1m", "3m", "6m", "1y")
SORT_FIELDS = {"code", "name", *(f"return_{window}" for window in RETURN_WINDOWS)}
QUALITY_GRADES = {"normal", "warning", "degraded", "unknown"}


@dataclass(frozen=True)
class FundSearchQuery:
    q: str = ""
    fund_type: str | None = None
    theme: str | None = None
    exchange_traded: bool | None = None
    purchase_status: str | None = None
    quality: str | None = None
    sort: str = "code"
    direction: str = "asc"
    page: int = 1
    page_size: int = 25


class FundExplorerIndex:
    """Read-only, hot-reloadable union of market observations and the M2 catalog."""

    def __init__(
        self,
        report_path: Path | str,
        *,
        catalog_cache: FundCache | None = None,
    ):
        self.report_path = Path(report_path).expanduser().resolve()
        self.catalog_cache = catalog_cache
        self._fingerprint: (
            tuple[tuple[int, int] | None, tuple[int, int] | None] | None
        ) = None
        self._failed_fingerprint: (
            tuple[tuple[int, int] | None, tuple[int, int] | None] | None
        ) = None
        self._items: tuple[dict[str, Any], ...] = ()
        self._by_code: dict[str, dict[str, Any]] = {}
        self._metadata: dict[str, Any] = {}
        self._warnings: list[str] = []
        self._index_stale = False
        self.load_count = 0

    def search(self, query: FundSearchQuery) -> dict[str, Any]:
        self._validate_query(query)
        self._ensure_loaded()

        query_text = query.q.strip().casefold()
        filtered = [
            item
            for item in self._items
            if self._matches(
                item,
                query_text=query_text,
                fund_type=query.fund_type,
                theme=query.theme,
                exchange_traded=query.exchange_traded,
                purchase_status=query.purchase_status,
                quality=query.quality,
            )
        ]
        ordered = self._sort(filtered, field=query.sort, direction=query.direction)
        total = len(ordered)
        start = (query.page - 1) * query.page_size
        end = start + query.page_size
        items = ordered[start:end]

        return {
            "availability": self._availability(),
            "items": items,
            "page": query.page,
            "page_size": query.page_size,
            "total": total,
            "total_pages": math.ceil(total / query.page_size) if total else 0,
            "facets": self._facets(filtered),
            "as_of": self._metadata.get("as_of"),
            "source": self._metadata.get("source"),
            "data_quality_grade": self._metadata.get("data_quality_grade", "unknown"),
            "index_stale": self._index_stale,
            "warnings": list(self._warnings),
        }

    def get(self, code: object) -> dict[str, Any] | None:
        self._ensure_loaded()
        normalized = normalize_fund_code(code)
        item = self._by_code.get(normalized)
        return dict(item) if item is not None else None

    def _ensure_loaded(self) -> None:
        report_fingerprint = _file_fingerprint(self.report_path)
        cache_fingerprint = (
            _file_fingerprint(self.catalog_cache.path)
            if self.catalog_cache is not None
            else None
        )
        fingerprint = (report_fingerprint, cache_fingerprint)
        if fingerprint == self._fingerprint:
            self._warnings = (
                ["fund_explorer_source_missing"]
                if not self._items and report_fingerprint is None
                else []
            )
            self._index_stale = False
            return
        if fingerprint == self._failed_fingerprint:
            return
        if (
            report_fingerprint is None
            and self._items
            and self._fingerprint is not None
            and self._fingerprint[0] is not None
        ):
            self._warnings = ["fund_explorer_source_missing_using_last_good_index"]
            self._index_stale = True
            return

        try:
            payload: dict[str, Any] = {}
            if report_fingerprint is not None:
                loaded = json.loads(self.report_path.read_text(encoding="utf-8"))
                if not isinstance(loaded, dict):
                    raise ValueError("market report must be a JSON object")
                payload = loaded
            market_items = self._build_items(payload)
            catalog, purchase_rules = self._load_reference_data()
            items = self._merge_reference_data(
                market_items,
                catalog=catalog,
                purchase_rules=purchase_rules,
            )
        except (json.JSONDecodeError, OSError, sqlite3.Error, TypeError, ValueError) as exc:
            self._failed_fingerprint = fingerprint
            self._warnings = [f"fund_explorer_index_reload_failed:{type(exc).__name__}"]
            self._index_stale = bool(self._items)
            return

        if not items:
            self._items = ()
            self._by_code = {}
            self._metadata = {}
            self._fingerprint = fingerprint
            self._failed_fingerprint = None
            self._warnings = ["fund_explorer_source_missing"]
            self._index_stale = False
            self.load_count += 1
            return

        self._items = tuple(items)
        self._by_code = {item["code"]: item for item in items}
        quality_summary = payload.get("data_quality_summary")
        quality = quality_summary.get("grade") if isinstance(quality_summary, dict) else None
        catalog_as_of = max(
            (_text(entry.as_of) for entry in catalog if _text(entry.as_of)),
            default="",
        )
        self._metadata = {
            "as_of": catalog_as_of or _text(payload.get("as_of")) or None,
            "source": (
                "fund_profile_catalog"
                if catalog
                else _text(payload.get("source")) or "unknown"
            ),
            "data_quality_grade": (
                "warning"
                if any(entry.stale for entry in catalog)
                else quality if quality in QUALITY_GRADES else "normal" if catalog else "unknown"
            ),
        }
        self._fingerprint = fingerprint
        self._failed_fingerprint = None
        self._warnings = []
        self._index_stale = False
        self.load_count += 1

    def _load_reference_data(
        self,
    ) -> tuple[list[FundCatalogEntry], list[FundTradingRule]]:
        if self.catalog_cache is None:
            return [], []
        catalog = self.catalog_cache.load_catalog_entries()
        if not catalog:
            catalog = self.catalog_cache.load_catalog_entries(allow_stale=True)
        purchase_rules = self.catalog_cache.load_purchase_statuses()
        if not purchase_rules:
            purchase_rules = self.catalog_cache.load_purchase_statuses(allow_stale=True)
        return catalog, purchase_rules

    @staticmethod
    def _merge_reference_data(
        market_items: list[dict[str, Any]],
        *,
        catalog: list[FundCatalogEntry],
        purchase_rules: list[FundTradingRule],
    ) -> list[dict[str, Any]]:
        by_code = {item["code"]: dict(item) for item in market_items}
        for entry in catalog:
            existing = by_code.get(entry.code)
            if existing is None:
                existing = {
                    "code": entry.code,
                    "primary_theme": "unknown",
                    "themes": [],
                    "classification_confidence": None,
                    "nav": None,
                    "scale": None,
                    "returns": {},
                    "valuation_date": None,
                    "data_quality_grade": "warning" if entry.stale else "normal",
                }
                by_code[entry.code] = existing
            existing.update(
                {
                    "name": entry.name,
                    "fund_type": _text(entry.fund_type) or "unknown",
                    "exchange_traded": entry.exchange_traded,
                    "source": entry.source,
                    "as_of": entry.as_of,
                    "updated_at": entry.updated_at,
                    "expires_at": entry.expires_at,
                    "stale": bool(existing.get("stale")) or entry.stale,
                }
            )
            if existing["stale"] and existing.get("data_quality_grade") == "normal":
                existing["data_quality_grade"] = "warning"

        for rule in purchase_rules:
            item = by_code.get(rule.code)
            if item is None:
                continue
            if status := _text(rule.purchase_status):
                item["purchase_status"] = status
            if status := _text(rule.redemption_status):
                item["redemption_status"] = status
            if rule.stale:
                item["stale"] = True
                if item.get("data_quality_grade") == "normal":
                    item["data_quality_grade"] = "warning"
        return list(by_code.values())

    @staticmethod
    def _build_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
        classifications = {
            normalize_fund_code(item.get("code")): item
            for item in payload.get("classifications") or []
            if isinstance(item, dict) and normalize_fund_code(item.get("code"))
        }
        items: list[dict[str, Any]] = []
        for record in payload.get("records") or []:
            if not isinstance(record, dict):
                continue
            code = normalize_fund_code(record.get("code"))
            if len(code) != 6 or not code.isdigit():
                continue
            metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
            classification = classifications.get(code, {})
            themes = _themes(classification.get("themes"))
            primary_theme = _text(classification.get("primary_theme")) or "unknown"
            stale = bool(metadata.get("stale"))
            quality = _text(metadata.get("data_quality_grade"))
            if quality not in QUALITY_GRADES:
                quality = "warning" if stale else "normal"
            returns_payload = metadata.get("returns") if isinstance(metadata.get("returns"), dict) else {}
            returns = {
                window: value
                for window in RETURN_WINDOWS
                if (value := _number(returns_payload.get(window))) is not None
            }
            items.append(
                {
                    "code": code,
                    "name": _text(record.get("name")),
                    "fund_type": _text(record.get("fund_type")) or "unknown",
                    "primary_theme": primary_theme,
                    "themes": themes,
                    "classification_confidence": _number(classification.get("confidence")),
                    "nav": _number(record.get("nav")),
                    "scale": _number(record.get("scale")),
                    "exchange_traded": bool(record.get("exchange_traded")),
                    "returns": returns,
                    "source": _text(record.get("source")) or _text(payload.get("source")) or "unknown",
                    "as_of": _text(record.get("as_of")) or _text(payload.get("as_of")) or None,
                    "valuation_date": _text(record.get("valuation_date")) or None,
                    "updated_at": _text(metadata.get("updated_at")) or None,
                    "expires_at": _text(metadata.get("expires_at")) or None,
                    "stale": stale,
                    "data_quality_grade": quality,
                }
            )
        return items

    @staticmethod
    def _validate_query(query: FundSearchQuery) -> None:
        if query.page < 1:
            raise ValueError("page must be at least 1")
        if not 1 <= query.page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        if query.sort not in SORT_FIELDS:
            raise ValueError(f"unsupported sort: {query.sort}")
        if query.direction not in {"asc", "desc"}:
            raise ValueError(f"unsupported direction: {query.direction}")
        if query.quality is not None and query.quality not in QUALITY_GRADES:
            raise ValueError(f"unsupported quality: {query.quality}")

    @staticmethod
    def _matches(
        item: dict[str, Any],
        *,
        query_text: str,
        fund_type: str | None,
        theme: str | None,
        exchange_traded: bool | None,
        purchase_status: str | None,
        quality: str | None,
    ) -> bool:
        if query_text and query_text not in f"{item['code']} {item['name']}".casefold():
            return False
        if fund_type and item["fund_type"] != fund_type:
            return False
        if theme and theme not in item["themes"]:
            return False
        if exchange_traded is not None and item["exchange_traded"] is not exchange_traded:
            return False
        if purchase_status and item.get("purchase_status") != purchase_status:
            return False
        if quality and item["data_quality_grade"] != quality:
            return False
        return True

    @staticmethod
    def _sort(items: list[dict[str, Any]], *, field: str, direction: str) -> list[dict[str, Any]]:
        if field.startswith("return_"):
            window = field.removeprefix("return_")
            available = [item for item in items if item["returns"].get(window) is not None]
            missing = [item for item in items if item["returns"].get(window) is None]
            available.sort(
                key=lambda item: item["returns"][window],
                reverse=direction == "desc",
            )
            return [*available, *missing]
        ordered = list(items)
        ordered.sort(
            key=lambda item: str(item[field]).casefold(),
            reverse=direction == "desc",
        )
        return ordered

    @staticmethod
    def _facets(items: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
        fund_types = Counter(item["fund_type"] for item in items)
        themes = Counter(theme for item in items for theme in item["themes"])
        exchange_traded = Counter(str(item["exchange_traded"]).lower() for item in items)
        qualities = Counter(item["data_quality_grade"] for item in items)
        purchase_statuses = Counter(
            status for item in items if (status := _text(item.get("purchase_status")))
        )
        return {
            "fund_types": dict(sorted(fund_types.items())),
            "themes": dict(sorted(themes.items())),
            "exchange_traded": {
                "true": exchange_traded.get("true", 0),
                "false": exchange_traded.get("false", 0),
            },
            "qualities": dict(sorted(qualities.items())),
            "purchase_statuses": dict(sorted(purchase_statuses.items())),
        }

    def _availability(self) -> str:
        if self._items or (
            self._fingerprint is not None
            and self._fingerprint[0] is not None
        ):
            return "available"
        return "missing"


def _text(value: object) -> str:
    return str(value or "").strip()


def _number(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _themes(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return list(dict.fromkeys(text for item in value if (text := _text(item))))


def _file_fingerprint(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size
