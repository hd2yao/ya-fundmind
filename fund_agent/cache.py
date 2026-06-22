from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from .models import FundRecord


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
                    source TEXT NOT NULL,
                    as_of TEXT NOT NULL,
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
                            code, nav_date, nav, source, as_of, updated_at, expires_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(code, nav_date, source) DO UPDATE SET
                            nav = excluded.nav,
                            as_of = excluded.as_of,
                            updated_at = excluded.updated_at,
                            expires_at = excluded.expires_at
                        """,
                        (code, fund.nav_date, fund.nav, fund.source, as_of, updated_at, expires_at),
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


def _utc_now(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
