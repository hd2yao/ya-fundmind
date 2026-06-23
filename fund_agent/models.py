from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FundRecord:
    code: str
    name: str
    category: str
    nav: float | None = None
    nav_date: str | None = None
    valuation_date: str | None = None
    returns: dict[str, float] = field(default_factory=dict)
    scale_billion: float | None = None
    manager: str | None = None
    fee_rate: float | None = None
    exchange_traded: bool = False
    price: float | None = None
    target_etf: str | None = None
    proxy_symbol: str | None = None
    source: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderWarning:
    code: str
    message: str
    severity: str = "warning"
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderHealth:
    provider: str
    started_at: str
    finished_at: str
    duration_ms: int
    provider_version: str | None = None
    live_row_count: int = 0
    mapped_row_count: int = 0
    skipped_row_count: int = 0
    cache_write_count: int = 0
    fallback_used: bool = False
    fallback_reason: str | None = None
    fallback_source: str | None = None
    watchlist_requested_count: int = 0
    watchlist_matched_count: int = 0
    watchlist_missing_codes: tuple[str, ...] = ()
    warnings: tuple[ProviderWarning, ...] = ()


@dataclass(frozen=True)
class ScoreBreakdown:
    return_quality: float
    trend_quality: float
    momentum_confirmation: float
    risk_adjusted: float
    scale_quality: float
    anti_sprint_penalty: float


@dataclass(frozen=True)
class ScoredFund:
    fund: FundRecord
    total_score: float
    breakdown: ScoreBreakdown
    evidence_label: str
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValuationResult:
    fund: FundRecord
    method: str
    estimated_value: float | None
    confidence: str
    notes: tuple[str, ...] = ()
