from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from .models import FundDetail, FundNavPoint, FundRecord


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
        if not allow_stale:
            clauses.append("expires_at >= ?")
            params.append(current_time)
        where = f"WHERE {' AND '.join(clauses)}"
        with self._connect() as conn:
            rows = conn.execute(f"SELECT * FROM fund_navs {where} ORDER BY nav_date", params).fetchall()
        return [self._row_to_nav_point(row, current_time=current_time) for row in rows]

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


def _utc_now(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
