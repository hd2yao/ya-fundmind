from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    quality: str | None = None
    sort: str = "code"
    direction: str = "asc"
    page: int = 1
    page_size: int = 25


class FundExplorerIndex:
    """Read-only, hot-reloadable index over the latest market artifact."""

    def __init__(self, report_path: Path | str):
        self.report_path = Path(report_path).expanduser().resolve()
        self._fingerprint: tuple[int, int] | None = None
        self._failed_fingerprint: tuple[int, int] | None = None
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
        try:
            stat = self.report_path.stat()
        except OSError:
            if self._items:
                self._warnings = ["fund_explorer_source_missing_using_last_good_index"]
                self._index_stale = True
            else:
                self._warnings = ["fund_explorer_source_missing"]
                self._index_stale = False
            return

        fingerprint = (stat.st_mtime_ns, stat.st_size)
        if fingerprint == self._fingerprint:
            self._warnings = []
            self._index_stale = False
            return
        if fingerprint == self._failed_fingerprint:
            return

        try:
            payload = json.loads(self.report_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("market report must be a JSON object")
            items = self._build_items(payload)
        except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
            self._failed_fingerprint = fingerprint
            self._warnings = [f"fund_explorer_index_reload_failed:{type(exc).__name__}"]
            self._index_stale = bool(self._items)
            return

        self._items = tuple(items)
        self._by_code = {item["code"]: item for item in items}
        quality_summary = payload.get("data_quality_summary")
        quality = quality_summary.get("grade") if isinstance(quality_summary, dict) else None
        self._metadata = {
            "as_of": _text(payload.get("as_of")) or None,
            "source": _text(payload.get("source")) or "unknown",
            "data_quality_grade": quality if quality in QUALITY_GRADES else "unknown",
        }
        self._fingerprint = fingerprint
        self._failed_fingerprint = None
        self._warnings = []
        self._index_stale = False
        self.load_count += 1

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
        return {
            "fund_types": dict(sorted(fund_types.items())),
            "themes": dict(sorted(themes.items())),
            "exchange_traded": {
                "true": exchange_traded.get("true", 0),
                "false": exchange_traded.get("false", 0),
            },
            "qualities": dict(sorted(qualities.items())),
        }

    def _availability(self) -> str:
        if self._fingerprint is not None or self._items:
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
