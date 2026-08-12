from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from .models import (
    FundCatalogEntry,
    FundDetail,
    FundFee,
    FundNavPoint,
    FundProfile,
    FundRecord,
    FundTradingRule,
    MarketEntity,
    MarketSeriesPoint,
)


@dataclass(frozen=True)
class CacheRecordStatus:
    source: str
    as_of: str
    updated_at: str
    expires_at: str
    stale: bool


class FundCache:
    def __init__(self, path: Path | str = Path("data/cache/funds.sqlite")):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS fund_basics (
                    code TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    nav REAL,
                    nav_date TEXT,
                    valuation_date TEXT,
                    returns_json TEXT NOT NULL,
                    scale_billion REAL,
                    manager TEXT,
                    fee_rate REAL,
                    exchange_traded INTEGER NOT NULL,
                    price REAL,
                    target_etf TEXT,
                    proxy_symbol TEXT,
                    source TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    PRIMARY KEY (code, as_of)
                );

                CREATE TABLE IF NOT EXISTS fund_navs (
                    code TEXT NOT NULL,
                    nav_date TEXT NOT NULL,
                    nav REAL,
                    accumulated_nav REAL,
                    daily_return REAL,
                    source TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    PRIMARY KEY (code, nav_date, source)
                );

                CREATE TABLE IF NOT EXISTS fund_valuations (
                    code TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    method TEXT NOT NULL,
                    estimated_value REAL,
                    confidence TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    PRIMARY KEY (code, as_of, method)
                );

                CREATE TABLE IF NOT EXISTS fund_details (
                    code TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    detail_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    PRIMARY KEY (code, as_of, source)
                );

                CREATE TABLE IF NOT EXISTS fund_catalog_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    as_of TEXT NOT NULL,
                    source TEXT NOT NULL,
                    entry_count INTEGER NOT NULL,
                    active INTEGER NOT NULL DEFAULT 0,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );

                CREATE UNIQUE INDEX IF NOT EXISTS fund_catalog_one_active
                ON fund_catalog_snapshots(active) WHERE active = 1;

                CREATE TABLE IF NOT EXISTS fund_catalog_entries (
                    snapshot_id TEXT NOT NULL,
                    code TEXT NOT NULL,
                    name TEXT NOT NULL,
                    fund_type TEXT,
                    exchange_traded INTEGER NOT NULL DEFAULT 0,
                    catalog_sources_json TEXT NOT NULL DEFAULT '[]',
                    source TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (snapshot_id, code)
                );

                CREATE TABLE IF NOT EXISTS fund_purchase_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    as_of TEXT NOT NULL,
                    source TEXT NOT NULL,
                    entry_count INTEGER NOT NULL,
                    active INTEGER NOT NULL DEFAULT 0,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );

                CREATE UNIQUE INDEX IF NOT EXISTS fund_purchase_one_active
                ON fund_purchase_snapshots(active) WHERE active = 1;

                CREATE TABLE IF NOT EXISTS fund_purchase_statuses (
                    snapshot_id TEXT NOT NULL,
                    code TEXT NOT NULL,
                    rule_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (snapshot_id, code)
                );

                CREATE TABLE IF NOT EXISTS fund_profiles (
                    code TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    profile_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    PRIMARY KEY (code, as_of, source)
                );

                CREATE TABLE IF NOT EXISTS fund_trading_rules (
                    code TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    rule_json TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    PRIMARY KEY (code, as_of, source)
                );

                CREATE TABLE IF NOT EXISTS fund_fees (
                    code TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    source TEXT NOT NULL,
                    fee_index INTEGER NOT NULL,
                    fee_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    PRIMARY KEY (code, as_of, source, fee_index)
                );

                CREATE TABLE IF NOT EXISTS market_series (
                    symbol TEXT NOT NULL,
                    series_type TEXT NOT NULL,
                    series_date TEXT NOT NULL,
                    name TEXT NOT NULL,
                    open REAL,
                    close REAL,
                    high REAL,
                    low REAL,
                    volume REAL,
                    turnover REAL,
                    change_pct REAL,
                    source TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    PRIMARY KEY (symbol, series_type, series_date, source)
                );

                CREATE TABLE IF NOT EXISTS market_entities (
                    entity_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    latest REAL,
                    change_pct REAL,
                    market_cap REAL,
                    turnover_rate REAL,
                    rise_count INTEGER,
                    fall_count INTEGER,
                    leader_name TEXT,
                    leader_change_pct REAL,
                    source TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    PRIMARY KEY (entity_type, symbol, source)
                );
                """
            )
            _ensure_column(conn, "fund_navs", "accumulated_nav", "REAL")
            _ensure_column(conn, "fund_navs", "daily_return", "REAL")
            _ensure_column(conn, "fund_navs", "metadata_json", "TEXT NOT NULL DEFAULT '{}'")

    def table_names(self) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        return {str(row["name"]) for row in rows}

    def upsert_funds(
        self,
        funds: Iterable[FundRecord],
        *,
        as_of: str,
        ttl_days: int = 1,
        now: datetime | None = None,
    ) -> None:
        updated_at = _utc_now(now).isoformat()
        expires_at = (_utc_now(now) + timedelta(days=ttl_days)).isoformat()
        with self._connect() as conn:
            for fund in funds:
                code = fund.code.strip()
                conn.execute(
                    """
                    INSERT INTO fund_basics (
                        code, as_of, name, category, nav, nav_date, valuation_date,
                        returns_json, scale_billion, manager, fee_rate,
                        exchange_traded, price, target_etf, proxy_symbol, source, metadata_json,
                        updated_at, expires_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(code, as_of) DO UPDATE SET
                        name = excluded.name,
                        category = excluded.category,
                        nav = excluded.nav,
                        nav_date = excluded.nav_date,
                        valuation_date = excluded.valuation_date,
                        returns_json = excluded.returns_json,
                        scale_billion = excluded.scale_billion,
                        manager = excluded.manager,
                        fee_rate = excluded.fee_rate,
                        exchange_traded = excluded.exchange_traded,
                        price = excluded.price,
                        target_etf = excluded.target_etf,
                        proxy_symbol = excluded.proxy_symbol,
                        source = excluded.source,
                        metadata_json = excluded.metadata_json,
                        updated_at = excluded.updated_at,
                        expires_at = excluded.expires_at
                        """,
                    (
                        code,
                        as_of,
                        fund.name,
                        fund.category,
                        fund.nav,
                        fund.nav_date,
                        fund.valuation_date,
                        json.dumps(fund.returns, ensure_ascii=False, sort_keys=True),
                        fund.scale_billion,
                        fund.manager,
                        fund.fee_rate,
                        1 if fund.exchange_traded else 0,
                        fund.price,
                        fund.target_etf or None,
                        fund.proxy_symbol or None,
                        fund.source,
                        json.dumps(fund.metadata, ensure_ascii=False, sort_keys=True),
                        updated_at,
                        expires_at,
                    ),
                )
                if fund.nav is not None and fund.nav_date:
                    conn.execute(
                        """
                        INSERT INTO fund_navs (
                            code, nav_date, nav, accumulated_nav, daily_return,
                            source, as_of, metadata_json, updated_at, expires_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(code, nav_date, source) DO UPDATE SET
                            nav = excluded.nav,
                            accumulated_nav = excluded.accumulated_nav,
                            daily_return = excluded.daily_return,
                            as_of = excluded.as_of,
                            metadata_json = excluded.metadata_json,
                            updated_at = excluded.updated_at,
                            expires_at = excluded.expires_at
                        WHERE instr(fund_navs.metadata_json, 'fund_nav_history') = 0
                        """,
                        (
                            code,
                            fund.nav_date,
                            fund.nav,
                            None,
                            None,
                            fund.source,
                            as_of,
                            "{}",
                            updated_at,
                            expires_at,
                        ),
                    )

    def load_funds(
        self,
        *,
        as_of: str | None = None,
        allow_stale: bool = False,
        now: datetime | None = None,
    ) -> list[FundRecord]:
        current_time = _utc_now(now).isoformat()
        clauses: list[str] = []
        params: list[object] = []
        if as_of is not None:
            clauses.append("as_of = ?")
            params.append(as_of)
        if not allow_stale:
            clauses.append("expires_at >= ?")
            params.append(current_time)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM fund_basics {where} ORDER BY code"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_fund(row, current_time=current_time) for row in rows]

    def upsert_fund_details(
        self,
        details: Iterable[FundDetail],
        *,
        as_of: str,
        ttl_days: int = 30,
        now: datetime | None = None,
    ) -> None:
        updated_at = _utc_now(now).isoformat()
        expires_at = (_utc_now(now) + timedelta(days=ttl_days)).isoformat()
        with self._connect() as conn:
            for detail in details:
                code = detail.code.strip()
                payload = {
                    "code": code,
                    "name": detail.name,
                    "fund_type": detail.fund_type,
                    "fund_company": detail.fund_company,
                    "fund_manager": detail.fund_manager,
                    "inception_date": detail.inception_date,
                    "scale": detail.scale,
                    "rating": detail.rating,
                    "source": detail.source,
                    "as_of": detail.as_of or as_of,
                    "updated_at": detail.updated_at or updated_at,
                    "metadata": detail.metadata,
                }
                conn.execute(
                    """
                    INSERT INTO fund_details (
                        code, as_of, detail_json, source, updated_at, expires_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(code, as_of, source) DO UPDATE SET
                        detail_json = excluded.detail_json,
                        updated_at = excluded.updated_at,
                        expires_at = excluded.expires_at
                    """,
                    (
                        code,
                        as_of,
                        json.dumps(payload, ensure_ascii=False, sort_keys=True),
                        detail.source,
                        updated_at,
                        expires_at,
                    ),
                )

    def load_fund_details(
        self,
        *,
        code: str | None = None,
        as_of: str | None = None,
        allow_stale: bool = False,
        now: datetime | None = None,
    ) -> list[FundDetail]:
        current_time = _utc_now(now).isoformat()
        clauses: list[str] = []
        params: list[object] = []
        if code is not None:
            clauses.append("code = ?")
            params.append(code.strip())
        if as_of is not None:
            clauses.append("as_of = ?")
            params.append(as_of)
        if not allow_stale:
            clauses.append("expires_at >= ?")
            params.append(current_time)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(f"SELECT * FROM fund_details {where} ORDER BY code", params).fetchall()
        return [self._row_to_detail(row, current_time=current_time) for row in rows]

    def replace_fund_catalog_snapshot(
        self,
        entries: Iterable[FundCatalogEntry],
        *,
        snapshot_id: str,
        as_of: str,
        ttl_days: int = 1,
        minimum_entry_count: int = 1,
        raw_entry_count: int | None = None,
        minimum_mapped_ratio: float = 0.0,
        now: datetime | None = None,
        metadata: dict | None = None,
    ) -> None:
        materialized = list(entries)
        if len(materialized) < minimum_entry_count:
            raise ValueError(
                f"catalog snapshot did not reach minimum entry count: "
                f"{len(materialized)} < {minimum_entry_count}"
            )
        mapped_ratio = _validate_snapshot_ratio(
            mapped_count=len(materialized),
            raw_entry_count=raw_entry_count,
            minimum_mapped_ratio=minimum_mapped_ratio,
            snapshot_kind="catalog",
        )
        codes = [entry.code.strip() for entry in materialized]
        if any(len(code) != 6 or not code.isdigit() for code in codes):
            raise ValueError("catalog snapshot contains an invalid six-digit fund code")
        if len(codes) != len(set(codes)):
            raise ValueError("catalog snapshot contains duplicate fund codes")
        updated_at = _utc_now(now).isoformat()
        expires_at = (_utc_now(now) + timedelta(days=ttl_days)).isoformat()
        source = materialized[0].source.removeprefix("cache:")
        with self._connect() as conn:
            conn.execute("UPDATE fund_catalog_snapshots SET active = 0 WHERE active = 1")
            conn.execute(
                """
                INSERT INTO fund_catalog_snapshots (
                    snapshot_id, as_of, source, entry_count, active,
                    metadata_json, updated_at, expires_at
                ) VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    as_of,
                    source,
                    len(materialized),
                    json.dumps(
                        {
                            **(metadata or {}),
                            "raw_entry_count": raw_entry_count,
                            "mapped_entry_count": len(materialized),
                            "mapped_ratio": mapped_ratio,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    updated_at,
                    expires_at,
                ),
            )
            conn.executemany(
                """
                INSERT INTO fund_catalog_entries (
                    snapshot_id, code, name, fund_type, exchange_traded,
                    catalog_sources_json, source, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        snapshot_id,
                        entry.code.strip(),
                        entry.name,
                        entry.fund_type,
                        1 if entry.exchange_traded else 0,
                        json.dumps(entry.catalog_sources, ensure_ascii=False),
                        entry.source.removeprefix("cache:"),
                        json.dumps(entry.metadata, ensure_ascii=False, sort_keys=True),
                    )
                    for entry in materialized
                ],
            )

    def load_catalog_entries(
        self,
        *,
        code: str | None = None,
        allow_stale: bool = False,
        now: datetime | None = None,
    ) -> list[FundCatalogEntry]:
        current_time = _utc_now(now).isoformat()
        clauses = ["snapshot.active = 1"]
        params: list[object] = []
        if code is not None:
            clauses.append("entry.code = ?")
            params.append(code.strip())
        if not allow_stale:
            clauses.append("snapshot.expires_at >= ?")
            params.append(current_time)
        where = " AND ".join(clauses)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT entry.*, snapshot.as_of, snapshot.updated_at, snapshot.expires_at
                FROM fund_catalog_entries AS entry
                JOIN fund_catalog_snapshots AS snapshot
                  ON snapshot.snapshot_id = entry.snapshot_id
                WHERE {where}
                ORDER BY entry.code
                """,
                params,
            ).fetchall()
        return [self._row_to_catalog_entry(row, current_time=current_time) for row in rows]

    def replace_purchase_snapshot(
        self,
        rules: Iterable[FundTradingRule],
        *,
        snapshot_id: str,
        as_of: str,
        ttl_days: int = 1,
        minimum_entry_count: int = 1,
        raw_entry_count: int | None = None,
        minimum_mapped_ratio: float = 0.0,
        now: datetime | None = None,
        metadata: dict | None = None,
    ) -> None:
        materialized = list(rules)
        if len(materialized) < minimum_entry_count:
            raise ValueError(
                f"purchase snapshot did not reach minimum entry count: "
                f"{len(materialized)} < {minimum_entry_count}"
            )
        mapped_ratio = _validate_snapshot_ratio(
            mapped_count=len(materialized),
            raw_entry_count=raw_entry_count,
            minimum_mapped_ratio=minimum_mapped_ratio,
            snapshot_kind="purchase",
        )
        codes = [rule.code.strip() for rule in materialized]
        if any(len(code) != 6 or not code.isdigit() for code in codes):
            raise ValueError("purchase snapshot contains an invalid six-digit fund code")
        if len(codes) != len(set(codes)):
            raise ValueError("purchase snapshot contains duplicate fund codes")
        updated_at = _utc_now(now).isoformat()
        expires_at = (_utc_now(now) + timedelta(days=ttl_days)).isoformat()
        source = materialized[0].source.removeprefix("cache:")
        with self._connect() as conn:
            conn.execute("UPDATE fund_purchase_snapshots SET active = 0 WHERE active = 1")
            conn.execute(
                """
                INSERT INTO fund_purchase_snapshots (
                    snapshot_id, as_of, source, entry_count, active,
                    metadata_json, updated_at, expires_at
                ) VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    as_of,
                    source,
                    len(materialized),
                    json.dumps(
                        {
                            **(metadata or {}),
                            "raw_entry_count": raw_entry_count,
                            "mapped_entry_count": len(materialized),
                            "mapped_ratio": mapped_ratio,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    updated_at,
                    expires_at,
                ),
            )
            conn.executemany(
                """
                INSERT INTO fund_purchase_statuses (
                    snapshot_id, code, rule_json, source, metadata_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        snapshot_id,
                        rule.code.strip(),
                        json.dumps(asdict(rule), ensure_ascii=False, sort_keys=True),
                        rule.source.removeprefix("cache:"),
                        json.dumps(rule.metadata, ensure_ascii=False, sort_keys=True),
                    )
                    for rule in materialized
                ],
            )

    def load_purchase_statuses(
        self,
        *,
        code: str | None = None,
        allow_stale: bool = False,
        now: datetime | None = None,
    ) -> list[FundTradingRule]:
        current_time = _utc_now(now).isoformat()
        clauses = ["snapshot.active = 1"]
        params: list[object] = []
        if code is not None:
            clauses.append("status.code = ?")
            params.append(code.strip())
        if not allow_stale:
            clauses.append("snapshot.expires_at >= ?")
            params.append(current_time)
        where = " AND ".join(clauses)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT status.*, snapshot.as_of, snapshot.updated_at, snapshot.expires_at
                FROM fund_purchase_statuses AS status
                JOIN fund_purchase_snapshots AS snapshot
                  ON snapshot.snapshot_id = status.snapshot_id
                WHERE {where}
                ORDER BY status.code
                """,
                params,
            ).fetchall()
        return [self._row_to_trading_rule(row, current_time=current_time) for row in rows]

    def upsert_fund_profiles(
        self,
        profiles: Iterable[FundProfile],
        *,
        as_of: str,
        ttl_days: int = 7,
        now: datetime | None = None,
    ) -> None:
        updated_at = _utc_now(now).isoformat()
        expires_at = (_utc_now(now) + timedelta(days=ttl_days)).isoformat()
        with self._connect() as conn:
            for profile in profiles:
                conn.execute(
                    """
                    INSERT INTO fund_profiles (
                        code, as_of, profile_json, source, updated_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(code, as_of, source) DO UPDATE SET
                        profile_json = excluded.profile_json,
                        updated_at = excluded.updated_at,
                        expires_at = excluded.expires_at
                    """,
                    (
                        profile.code.strip(),
                        as_of,
                        json.dumps(asdict(profile), ensure_ascii=False, sort_keys=True),
                        profile.source.removeprefix("cache:"),
                        updated_at,
                        expires_at,
                    ),
                )

    def load_fund_profiles(
        self,
        *,
        code: str,
        allow_stale: bool = False,
        now: datetime | None = None,
    ) -> list[FundProfile]:
        current_time = _utc_now(now).isoformat()
        clauses = ["code = ?"]
        params: list[object] = [code.strip()]
        if not allow_stale:
            clauses.append("expires_at >= ?")
            params.append(current_time)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM fund_profiles WHERE {' AND '.join(clauses)} ORDER BY as_of DESC",
                params,
            ).fetchall()
        return [self._row_to_profile(row, current_time=current_time) for row in rows]

    def upsert_fund_trading_rules(
        self,
        rules: Iterable[FundTradingRule],
        *,
        as_of: str,
        ttl_days: int = 7,
        now: datetime | None = None,
    ) -> None:
        updated_at = _utc_now(now).isoformat()
        expires_at = (_utc_now(now) + timedelta(days=ttl_days)).isoformat()
        with self._connect() as conn:
            for rule in rules:
                conn.execute(
                    """
                    INSERT INTO fund_trading_rules (
                        code, as_of, rule_json, source, updated_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(code, as_of, source) DO UPDATE SET
                        rule_json = excluded.rule_json,
                        updated_at = excluded.updated_at,
                        expires_at = excluded.expires_at
                    """,
                    (
                        rule.code.strip(),
                        as_of,
                        json.dumps(asdict(rule), ensure_ascii=False, sort_keys=True),
                        rule.source.removeprefix("cache:"),
                        updated_at,
                        expires_at,
                    ),
                )

    def load_fund_trading_rules(
        self,
        *,
        code: str,
        allow_stale: bool = False,
        now: datetime | None = None,
    ) -> list[FundTradingRule]:
        current_time = _utc_now(now).isoformat()
        clauses = ["code = ?"]
        params: list[object] = [code.strip()]
        if not allow_stale:
            clauses.append("expires_at >= ?")
            params.append(current_time)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM fund_trading_rules WHERE {' AND '.join(clauses)} ORDER BY as_of DESC",
                params,
            ).fetchall()
        return [self._row_to_trading_rule(row, current_time=current_time) for row in rows]

    def replace_fund_fees(
        self,
        code: str,
        fees: Iterable[FundFee],
        *,
        as_of: str,
        ttl_days: int = 7,
        now: datetime | None = None,
    ) -> None:
        materialized = list(fees)
        updated_at = _utc_now(now).isoformat()
        expires_at = (_utc_now(now) + timedelta(days=ttl_days)).isoformat()
        with self._connect() as conn:
            conn.execute("DELETE FROM fund_fees WHERE code = ? AND as_of = ?", (code.strip(), as_of))
            for fee_index, fee in enumerate(materialized):
                conn.execute(
                    """
                    INSERT INTO fund_fees (
                        code, as_of, source, fee_index, fee_json, updated_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        code.strip(),
                        as_of,
                        fee.source.removeprefix("cache:"),
                        fee_index,
                        json.dumps(asdict(fee), ensure_ascii=False, sort_keys=True),
                        updated_at,
                        expires_at,
                    ),
                )

    def load_fund_fees(
        self,
        *,
        code: str,
        allow_stale: bool = False,
        now: datetime | None = None,
    ) -> list[FundFee]:
        current_time = _utc_now(now).isoformat()
        clauses = ["code = ?"]
        params: list[object] = [code.strip()]
        if not allow_stale:
            clauses.append("expires_at >= ?")
            params.append(current_time)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM fund_fees WHERE {' AND '.join(clauses)} ORDER BY as_of DESC, fee_index",
                params,
            ).fetchall()
        if not rows:
            return []
        latest_as_of = rows[0]["as_of"]
        return [
            self._row_to_fee(row, current_time=current_time)
            for row in rows
            if row["as_of"] == latest_as_of
        ]

    def upsert_nav_points(
        self,
        nav_points: Iterable[FundNavPoint],
        *,
        as_of: str,
        ttl_days: int = 30,
        now: datetime | None = None,
    ) -> None:
        updated_at = _utc_now(now).isoformat()
        expires_at = (_utc_now(now) + timedelta(days=ttl_days)).isoformat()
        with self._connect() as conn:
            for point in nav_points:
                conn.execute(
                    """
                    INSERT INTO fund_navs (
                        code, nav_date, nav, accumulated_nav, daily_return,
                        source, as_of, metadata_json, updated_at, expires_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(code, nav_date, source) DO UPDATE SET
                        nav = excluded.nav,
                        accumulated_nav = excluded.accumulated_nav,
                        daily_return = excluded.daily_return,
                        as_of = excluded.as_of,
                        metadata_json = excluded.metadata_json,
                        updated_at = excluded.updated_at,
                        expires_at = excluded.expires_at
                    """,
                    (
                        point.code.strip(),
                        point.date,
                        point.unit_nav,
                        point.accumulated_nav,
                        point.daily_return,
                        point.source,
                        as_of,
                        json.dumps(point.metadata, ensure_ascii=False, sort_keys=True),
                        updated_at,
                        expires_at,
                    ),
                )

    def load_nav_points(
        self,
        *,
        code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        source: str | None = None,
        allow_stale: bool = False,
        now: datetime | None = None,
    ) -> list[FundNavPoint]:
        current_time = _utc_now(now).isoformat()
        clauses = ["code = ?"]
        params: list[object] = [code.strip()]
        if start_date is not None:
            clauses.append("nav_date >= ?")
            params.append(start_date)
        if end_date is not None:
            clauses.append("nav_date <= ?")
            params.append(end_date)
        if source is not None:
            clauses.append("source = ?")
            params.append(source.removeprefix("cache:"))
        if not allow_stale:
            clauses.append("expires_at >= ?")
            params.append(current_time)
        where = f"WHERE {' AND '.join(clauses)}"
        with self._connect() as conn:
            rows = conn.execute(f"SELECT * FROM fund_navs {where} ORDER BY nav_date", params).fetchall()
        return [self._row_to_nav_point(row, current_time=current_time) for row in rows]

    def upsert_market_series(
        self,
        points: Iterable[MarketSeriesPoint],
        *,
        as_of: str,
        ttl_days: int = 1,
        now: datetime | None = None,
    ) -> None:
        updated_at = _utc_now(now).isoformat()
        expires_at = (_utc_now(now) + timedelta(days=ttl_days)).isoformat()
        with self._connect() as conn:
            for point in points:
                conn.execute(
                    """
                    INSERT INTO market_series (
                        symbol, series_type, series_date, name,
                        open, close, high, low, volume, turnover, change_pct,
                        source, as_of, metadata_json, updated_at, expires_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol, series_type, series_date, source) DO UPDATE SET
                        name = excluded.name,
                        open = excluded.open,
                        close = excluded.close,
                        high = excluded.high,
                        low = excluded.low,
                        volume = excluded.volume,
                        turnover = excluded.turnover,
                        change_pct = excluded.change_pct,
                        as_of = excluded.as_of,
                        metadata_json = excluded.metadata_json,
                        updated_at = excluded.updated_at,
                        expires_at = excluded.expires_at
                    """,
                    (
                        point.symbol.strip(),
                        point.series_type,
                        point.date,
                        point.name,
                        point.open,
                        point.close,
                        point.high,
                        point.low,
                        point.volume,
                        point.turnover,
                        point.change_pct,
                        point.source.removeprefix("cache:"),
                        as_of,
                        json.dumps(point.metadata, ensure_ascii=False, sort_keys=True),
                        updated_at,
                        expires_at,
                    ),
                )

    def upsert_market_entities(
        self,
        entities: Iterable[MarketEntity],
        *,
        as_of: str,
        ttl_days: int = 1,
        now: datetime | None = None,
    ) -> None:
        updated_at = _utc_now(now).isoformat()
        expires_at = (_utc_now(now) + timedelta(days=ttl_days)).isoformat()
        with self._connect() as conn:
            for entity in entities:
                conn.execute(
                    """
                    INSERT INTO market_entities (
                        entity_type, symbol, name, latest, change_pct,
                        market_cap, turnover_rate, rise_count, fall_count,
                        leader_name, leader_change_pct, source, as_of,
                        metadata_json, updated_at, expires_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(entity_type, symbol, source) DO UPDATE SET
                        name = excluded.name,
                        latest = excluded.latest,
                        change_pct = excluded.change_pct,
                        market_cap = excluded.market_cap,
                        turnover_rate = excluded.turnover_rate,
                        rise_count = excluded.rise_count,
                        fall_count = excluded.fall_count,
                        leader_name = excluded.leader_name,
                        leader_change_pct = excluded.leader_change_pct,
                        as_of = excluded.as_of,
                        metadata_json = excluded.metadata_json,
                        updated_at = excluded.updated_at,
                        expires_at = excluded.expires_at
                    """,
                    (
                        entity.entity_type,
                        entity.symbol.strip(),
                        entity.name,
                        entity.latest,
                        entity.change_pct,
                        entity.market_cap,
                        entity.turnover_rate,
                        entity.rise_count,
                        entity.fall_count,
                        entity.leader_name,
                        entity.leader_change_pct,
                        entity.source.removeprefix("cache:"),
                        entity.as_of or as_of,
                        json.dumps(
                            entity.metadata,
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        updated_at,
                        expires_at,
                    ),
                )

    def load_market_entities(
        self,
        *,
        entity_type: str,
        source: str | None = None,
        allow_stale: bool = False,
        now: datetime | None = None,
    ) -> list[MarketEntity]:
        current_time = _utc_now(now).isoformat()
        clauses = ["entity_type = ?"]
        params: list[object] = [entity_type]
        if source is not None:
            clauses.append("source = ?")
            params.append(source.removeprefix("cache:"))
        if not allow_stale:
            clauses.append("expires_at >= ?")
            params.append(current_time)
        where = f"WHERE {' AND '.join(clauses)}"
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM market_entities {where} ORDER BY symbol",
                params,
            ).fetchall()
        return [
            self._row_to_market_entity(row, current_time=current_time)
            for row in rows
        ]

    def load_market_series(
        self,
        *,
        symbol: str,
        series_type: str,
        source: str | None = None,
        allow_stale: bool = False,
        now: datetime | None = None,
    ) -> list[MarketSeriesPoint]:
        current_time = _utc_now(now).isoformat()
        clauses = ["symbol = ?", "series_type = ?"]
        params: list[object] = [symbol.strip(), series_type]
        if source is not None:
            clauses.append("source = ?")
            params.append(source.removeprefix("cache:"))
        if not allow_stale:
            clauses.append("expires_at >= ?")
            params.append(current_time)
        where = f"WHERE {' AND '.join(clauses)}"
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM market_series {where} ORDER BY series_date",
                params,
            ).fetchall()
        return [
            self._row_to_market_series_point(row, current_time=current_time)
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_fund(self, row: sqlite3.Row, *, current_time: str) -> FundRecord:
        metadata = json.loads(row["metadata_json"] or "{}")
        source = str(row["source"])
        stale = str(row["expires_at"]) < current_time
        metadata.update(
            {
                "cache_source": source,
                "cache_as_of": row["as_of"],
                "updated_at": row["updated_at"],
                "expires_at": row["expires_at"],
                "stale": stale,
            }
        )
        return FundRecord(
            code=str(row["code"]).strip(),
            name=str(row["name"]),
            category=str(row["category"]),
            nav=row["nav"],
            nav_date=row["nav_date"],
            valuation_date=row["valuation_date"],
            returns=json.loads(row["returns_json"] or "{}"),
            scale_billion=row["scale_billion"],
            manager=row["manager"],
            fee_rate=row["fee_rate"],
            exchange_traded=bool(row["exchange_traded"]),
            price=row["price"],
            target_etf=row["target_etf"],
            proxy_symbol=row["proxy_symbol"],
            source=f"cache:{source}",
            metadata=metadata,
        )

    def _row_to_detail(self, row: sqlite3.Row, *, current_time: str) -> FundDetail:
        payload = json.loads(row["detail_json"] or "{}")
        metadata = dict(payload.get("metadata", {}))
        stale = str(row["expires_at"]) < current_time
        metadata.update(
            {
                "cache_source": row["source"],
                "cache_as_of": row["as_of"],
                "updated_at": row["updated_at"],
                "expires_at": row["expires_at"],
                "stale": stale,
            }
        )
        return FundDetail(
            code=str(row["code"]).strip(),
            name=str(payload.get("name", "")),
            fund_type=payload.get("fund_type"),
            fund_company=payload.get("fund_company"),
            fund_manager=payload.get("fund_manager"),
            inception_date=payload.get("inception_date"),
            scale=payload.get("scale"),
            rating=payload.get("rating"),
            source=f"cache:{row['source']}",
            as_of=row["as_of"],
            updated_at=row["updated_at"],
            metadata=metadata,
        )

    def _row_to_catalog_entry(
        self,
        row: sqlite3.Row,
        *,
        current_time: str,
    ) -> FundCatalogEntry:
        stale = str(row["expires_at"]) < current_time
        metadata = json.loads(row["metadata_json"] or "{}")
        metadata.update(
            {
                "cache_source": row["source"],
                "cache_as_of": row["as_of"],
                "snapshot_id": row["snapshot_id"],
                "updated_at": row["updated_at"],
                "expires_at": row["expires_at"],
                "stale": stale,
            }
        )
        return FundCatalogEntry(
            code=str(row["code"]).strip(),
            name=str(row["name"]),
            fund_type=row["fund_type"],
            exchange_traded=bool(row["exchange_traded"]),
            catalog_sources=tuple(json.loads(row["catalog_sources_json"] or "[]")),
            source=f"cache:{row['source']}",
            as_of=row["as_of"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
            stale=stale,
            metadata=metadata,
        )

    def _row_to_profile(self, row: sqlite3.Row, *, current_time: str) -> FundProfile:
        payload = json.loads(row["profile_json"] or "{}")
        stale = str(row["expires_at"]) < current_time
        metadata = dict(payload.get("metadata", {}))
        metadata.update(
            {
                "cache_source": row["source"],
                "cache_as_of": row["as_of"],
                "updated_at": row["updated_at"],
                "expires_at": row["expires_at"],
                "stale": stale,
            }
        )
        return FundProfile(
            code=str(row["code"]).strip(),
            name=payload.get("name"),
            full_name=payload.get("full_name"),
            fund_type=payload.get("fund_type"),
            fund_company=payload.get("fund_company"),
            custodian=payload.get("custodian"),
            fund_manager=payload.get("fund_manager"),
            issue_date=payload.get("issue_date"),
            inception_date=payload.get("inception_date"),
            asset_scale=payload.get("asset_scale"),
            asset_scale_unit=payload.get("asset_scale_unit"),
            share_scale=payload.get("share_scale"),
            share_scale_unit=payload.get("share_scale_unit"),
            benchmark=payload.get("benchmark"),
            tracking_target=payload.get("tracking_target"),
            source=f"cache:{row['source']}",
            as_of=row["as_of"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
            stale=stale,
            metadata=metadata,
        )

    def _row_to_trading_rule(
        self,
        row: sqlite3.Row,
        *,
        current_time: str,
    ) -> FundTradingRule:
        payload = json.loads(row["rule_json"] or "{}")
        stale = str(row["expires_at"]) < current_time
        metadata = dict(payload.get("metadata", {}))
        metadata.update(
            {
                "cache_source": row["source"],
                "cache_as_of": row["as_of"],
                "updated_at": row["updated_at"],
                "expires_at": row["expires_at"],
                "stale": stale,
            }
        )
        return FundTradingRule(
            code=str(row["code"]).strip(),
            purchase_status=payload.get("purchase_status"),
            redemption_status=payload.get("redemption_status"),
            next_open_date=payload.get("next_open_date"),
            minimum_purchase_amount=payload.get("minimum_purchase_amount"),
            daily_purchase_limit=payload.get("daily_purchase_limit"),
            confirmation_rule=payload.get("confirmation_rule"),
            source=f"cache:{row['source']}",
            as_of=row["as_of"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
            stale=stale,
            metadata=metadata,
        )

    def _row_to_fee(self, row: sqlite3.Row, *, current_time: str) -> FundFee:
        payload = json.loads(row["fee_json"] or "{}")
        stale = str(row["expires_at"]) < current_time
        metadata = dict(payload.get("metadata", {}))
        metadata.update(
            {
                "cache_source": row["source"],
                "cache_as_of": row["as_of"],
                "updated_at": row["updated_at"],
                "expires_at": row["expires_at"],
                "stale": stale,
            }
        )
        return FundFee(
            code=str(row["code"]).strip(),
            fee_type=str(payload.get("fee_type", "费率")),
            condition=payload.get("condition"),
            period=payload.get("period"),
            channel=payload.get("channel"),
            original_rate=payload.get("original_rate"),
            discounted_rate=payload.get("discounted_rate"),
            source=f"cache:{row['source']}",
            as_of=row["as_of"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
            stale=stale,
            metadata=metadata,
        )

    def _row_to_nav_point(self, row: sqlite3.Row, *, current_time: str) -> FundNavPoint:
        metadata = json.loads(row["metadata_json"] or "{}")
        stale = str(row["expires_at"]) < current_time
        metadata.update(
            {
                "cache_source": row["source"],
                "cache_as_of": row["as_of"],
                "updated_at": row["updated_at"],
                "expires_at": row["expires_at"],
                "stale": stale,
            }
        )
        return FundNavPoint(
            code=str(row["code"]).strip(),
            date=str(row["nav_date"]),
            unit_nav=row["nav"],
            accumulated_nav=row["accumulated_nav"],
            daily_return=row["daily_return"],
            source=f"cache:{row['source']}",
            updated_at=row["updated_at"],
            metadata=metadata,
        )

    def _row_to_market_series_point(
        self,
        row: sqlite3.Row,
        *,
        current_time: str,
    ) -> MarketSeriesPoint:
        metadata = json.loads(row["metadata_json"] or "{}")
        stale = str(row["expires_at"]) < current_time
        metadata.update(
            {
                "cache_source": row["source"],
                "cache_as_of": row["as_of"],
                "updated_at": row["updated_at"],
                "expires_at": row["expires_at"],
                "stale": stale,
            }
        )
        return MarketSeriesPoint(
            symbol=str(row["symbol"]),
            name=str(row["name"]),
            series_type=str(row["series_type"]),
            date=str(row["series_date"]),
            open=row["open"],
            close=row["close"],
            high=row["high"],
            low=row["low"],
            volume=row["volume"],
            turnover=row["turnover"],
            change_pct=row["change_pct"],
            source=f"cache:{row['source']}",
            updated_at=row["updated_at"],
            metadata=metadata,
        )

    def _row_to_market_entity(
        self,
        row: sqlite3.Row,
        *,
        current_time: str,
    ) -> MarketEntity:
        metadata = json.loads(row["metadata_json"] or "{}")
        stale = str(row["expires_at"]) < current_time
        metadata.update(
            {
                "cache_source": row["source"],
                "cache_as_of": row["as_of"],
                "updated_at": row["updated_at"],
                "expires_at": row["expires_at"],
                "stale": stale,
            }
        )
        return MarketEntity(
            symbol=str(row["symbol"]),
            name=str(row["name"]),
            entity_type=str(row["entity_type"]),
            latest=row["latest"],
            change_pct=row["change_pct"],
            market_cap=row["market_cap"],
            turnover_rate=row["turnover_rate"],
            rise_count=row["rise_count"],
            fall_count=row["fall_count"],
            leader_name=row["leader_name"],
            leader_change_pct=row["leader_change_pct"],
            source=f"cache:{row['source']}",
            as_of=row["as_of"],
            updated_at=row["updated_at"],
            metadata=metadata,
        )


def _utc_now(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _validate_snapshot_ratio(
    *,
    mapped_count: int,
    raw_entry_count: int | None,
    minimum_mapped_ratio: float,
    snapshot_kind: str,
) -> float | None:
    if not 0.0 <= minimum_mapped_ratio <= 1.0:
        raise ValueError("minimum mapped ratio must be between 0 and 1")
    if raw_entry_count is None:
        if minimum_mapped_ratio > 0:
            raise ValueError(
                f"{snapshot_kind} snapshot requires raw entry count for mapped-ratio validation"
            )
        return None
    if raw_entry_count < mapped_count or raw_entry_count < 0:
        raise ValueError(
            f"{snapshot_kind} snapshot raw entry count cannot be smaller than mapped count"
        )
    mapped_ratio = 1.0 if raw_entry_count == 0 else mapped_count / raw_entry_count
    if mapped_ratio < minimum_mapped_ratio:
        raise ValueError(
            f"{snapshot_kind} snapshot did not reach minimum mapped ratio: "
            f"{mapped_ratio:.4f} < {minimum_mapped_ratio:.4f}"
        )
    return mapped_ratio


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
