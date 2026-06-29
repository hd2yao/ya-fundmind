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
class FundDetail:
    code: str
    name: str
    fund_type: str | None = None
    fund_company: str | None = None
    fund_manager: str | None = None
    inception_date: str | None = None
    scale: float | None = None
    rating: str | None = None
    source: str = "unknown"
    as_of: str | None = None
    updated_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FundNavPoint:
    code: str
    date: str
    unit_nav: float | None = None
    accumulated_nav: float | None = None
    daily_return: float | None = None
    source: str = "unknown"
    updated_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SignalCandidate:
    signal_id: str
    source: str
    code: str
    category: str
    value: Any
    direction: str
    quality_grade: str
    eligible: bool
    excluded_reason: str | None
    evidence: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentScoreResult:
    code: str
    base_score: float | None
    experiment_score: float | None
    score_delta: float
    applied_signals: tuple[dict[str, Any], ...] = ()
    excluded_signals: tuple[dict[str, Any], ...] = ()
    confidence: str = "low"
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentRiskIssue:
    code: str
    issue_type: str
    severity: str
    source_signal: str
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderWarning:
    code: str
    message: str
    severity: str = "warning"
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized = str(self.severity or "warning").lower()
        if normalized == "error":
            normalized = "critical"
        if normalized not in {"info", "warning", "critical"}:
            normalized = "warning"
        object.__setattr__(self, "severity", normalized)


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
    cache_read_count: int = 0
    cache_write_count: int = 0
    fallback_used: bool = False
    fallback_reason: str | None = None
    fallback_source: str | None = None
    watchlist_requested_count: int = 0
    watchlist_matched_count: int = 0
    watchlist_missing_codes: tuple[str, ...] = ()
    warnings: tuple[ProviderWarning, ...] = ()
    endpoints: tuple[ProviderEndpointTrace, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_critical_warnings(self) -> bool:
        return any(warning.severity == "critical" for warning in self.warnings)


@dataclass(frozen=True)
class ProviderEndpointTrace:
    endpoint: str
    started_at: str
    finished_at: str
    duration_ms: int
    attempts: int = 1
    success: bool = True
    error: str | None = None
    timeout_seconds: float | None = None
    live_row_count: int = 0
    mapped_row_count: int = 0
    skipped_row_count: int = 0


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
