from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .cache import FundCache
from .market_intelligence import (
    build_market_intelligence_report,
    build_market_snapshot,
    fund_record_to_market_record,
    market_report_to_dict,
    render_market_intelligence_summary,
)
from .models import FundNavPoint, FundRecord
from .nav_summary import build_nav_history_windows_summary
from .providers import FixtureProvider, normalize_fund_code


HISTORICAL_BACKFILL_RUN_TYPE = "historical_backfill"
FIXTURE_BACKFILL_WARNING = "fixture_synthetic_backfill_not_real_history"


@dataclass(frozen=True)
class HistoricalBackfillResult:
    status: str
    report_path: Path
    summary_path: Path
    nav_summary_path: Path
    dates_processed: tuple[str, ...]
    market_snapshot_count: int
    nav_summary_count: int
    warnings: tuple[str, ...]


def run_historical_backfill(
    *,
    provider: str,
    start_date: str,
    end_date: str,
    output_dir: Path | str,
    funds_file: Path | str = Path("data/fixtures/funds.json"),
    cache_file: Path | str = Path("data/cache/funds.sqlite"),
    themes_config: Path | str = Path("configs/market_themes.yaml"),
    top_n: int = 20,
    min_theme_sample_size: int = 5,
    nav_windows: tuple[str, ...] = ("1m", "3m", "6m"),
) -> HistoricalBackfillResult:
    dates = tuple(_date_range(start_date, end_date))
    root = Path(output_dir)
    backfill_dir = root / "backfill"
    backfill_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    if provider == "fixture":
        warnings.append(FIXTURE_BACKFILL_WARNING)
        funds_by_date = {day: _fixture_funds(funds_file, as_of=day) for day in dates}
        nav_points_by_code = _fixture_nav_points_by_code(funds_by_date)
    elif provider == "cache":
        cache = FundCache(cache_file)
        funds_by_date = {day: cache.load_funds(as_of=day, allow_stale=True) for day in dates}
        fallback_funds = cache.load_funds(allow_stale=True)
        funds_by_date = {day: rows or fallback_funds for day, rows in funds_by_date.items()}
        nav_points_by_code = _cache_nav_points_by_code(cache, funds_by_date, start_date=start_date, end_date=end_date)
        if not any(funds_by_date.values()) and not any(nav_points_by_code.values()):
            warnings.append("cache_backfill_no_cached_data")
    else:
        raise ValueError(f"Unsupported historical backfill provider: {provider}")

    market_snapshot_count = 0
    for day in dates:
        funds = funds_by_date.get(day, [])
        if not funds:
            warnings.append(f"no_fund_rows_for_date:{day}")
            continue
        report = build_market_intelligence_report(
            [fund_record_to_market_record(fund, as_of=day) for fund in funds],
            as_of=day,
            source=provider,
            themes_config=themes_config,
            top_n=top_n,
            min_theme_sample_size=min_theme_sample_size,
            run_type=HISTORICAL_BACKFILL_RUN_TYPE,
        )
        snapshot_payload = _backfill_snapshot_payload(build_market_snapshot(report), provider=provider, warnings=warnings)
        _write_backfill_market_outputs(
            root,
            day=day,
            report_payload=market_report_to_dict(report),
            summary=render_market_intelligence_summary(report),
            snapshot_payload=snapshot_payload,
            warnings=warnings,
        )
        market_snapshot_count += 1

    nav_summary_payload = _build_nav_summary_payload(
        provider=provider,
        start_date=start_date,
        end_date=end_date,
        nav_points_by_code=nav_points_by_code,
        windows=nav_windows,
        warnings=warnings,
    )
    nav_summary_path = backfill_dir / "nav_history_summary.json"
    nav_summary_path.write_text(
        json.dumps(nav_summary_payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    status = "success" if market_snapshot_count or nav_summary_payload["nav_history_summary"] else "failed"
    report_payload = {
        "schema_version": "1.0",
        "generated_at": _utc_now(),
        "generator": "fund_agent.historical_backfill",
        "run_type": HISTORICAL_BACKFILL_RUN_TYPE,
        "provider": provider,
        "start_date": start_date,
        "end_date": end_date,
        "dates_processed": list(dates),
        "market_snapshot_count": market_snapshot_count,
        "nav_summary_count": len(nav_summary_payload["nav_history_summary"]),
        "warnings": list(dict.fromkeys(warnings)),
        "not_production_model": True,
        "main_score_changed": False,
        "main_risk_changed": False,
    }
    report_path = backfill_dir / "backfill_report.json"
    summary_path = backfill_dir / "backfill_summary.md"
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    summary_path.write_text(_render_backfill_summary(report_payload), encoding="utf-8")

    return HistoricalBackfillResult(
        status=status,
        report_path=report_path,
        summary_path=summary_path,
        nav_summary_path=nav_summary_path,
        dates_processed=dates,
        market_snapshot_count=market_snapshot_count,
        nav_summary_count=len(nav_summary_payload["nav_history_summary"]),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _date_range(start_date: str, end_date: str) -> list[str]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if end < start:
        raise ValueError("end_date must be greater than or equal to start_date")
    days = []
    current = start
    while current <= end:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def _fixture_funds(funds_file: Path | str, *, as_of: str) -> list[FundRecord]:
    provider = FixtureProvider(Path(funds_file))
    return [
        FundRecord(
            code=fund.code,
            name=fund.name,
            category=fund.category,
            nav=fund.nav,
            nav_date=as_of,
            valuation_date=as_of,
            returns=dict(fund.returns),
            scale_billion=fund.scale_billion,
            manager=fund.manager,
            fee_rate=fund.fee_rate,
            exchange_traded=fund.exchange_traded,
            price=fund.price,
            target_etf=fund.target_etf,
            proxy_symbol=fund.proxy_symbol,
            source="fixture:historical_backfill",
            metadata={
                **fund.metadata,
                "run_type": HISTORICAL_BACKFILL_RUN_TYPE,
                "backfill": True,
                "fixture_synthetic": True,
            },
        )
        for fund in provider.fetch_funds(as_of=as_of)
    ]


def _fixture_nav_points_by_code(funds_by_date: dict[str, list[FundRecord]]) -> dict[str, list[FundNavPoint]]:
    points: dict[str, list[FundNavPoint]] = {}
    for day, funds in funds_by_date.items():
        for fund in funds:
            if fund.nav is None:
                continue
            points.setdefault(fund.code, []).append(
                FundNavPoint(
                    code=fund.code,
                    date=day,
                    unit_nav=fund.nav,
                    accumulated_nav=fund.nav,
                    source="fixture:historical_backfill",
                    updated_at=_utc_now(),
                    metadata={
                        "run_type": HISTORICAL_BACKFILL_RUN_TYPE,
                        "backfill": True,
                        "fixture_synthetic": True,
                    },
                )
            )
    return points


def _cache_nav_points_by_code(
    cache: FundCache,
    funds_by_date: dict[str, list[FundRecord]],
    *,
    start_date: str,
    end_date: str,
) -> dict[str, list[FundNavPoint]]:
    codes = sorted({fund.code for funds in funds_by_date.values() for fund in funds})
    points: dict[str, list[FundNavPoint]] = {}
    for code in codes:
        rows = cache.load_nav_points(
            code=normalize_fund_code(code),
            start_date=start_date,
            end_date=end_date,
            allow_stale=True,
        )
        if rows:
            points[normalize_fund_code(code)] = rows
    return points


def _backfill_snapshot_payload(payload: dict[str, Any], *, provider: str, warnings: list[str]) -> dict[str, Any]:
    return {
        **payload,
        "run_type": HISTORICAL_BACKFILL_RUN_TYPE,
        "backfill": True,
        "historical_backfill": True,
        "live_daily": False,
        "source_mode": provider,
        "warnings": list(dict.fromkeys([*payload.get("warnings", []), *warnings])),
        "not_production_model": True,
        "main_score_changed": False,
        "main_risk_changed": False,
    }


def _write_backfill_market_outputs(
    root: Path,
    *,
    day: str,
    report_payload: dict[str, Any],
    summary: str,
    snapshot_payload: dict[str, Any],
    warnings: list[str],
) -> None:
    snapshots_dir = root / "market" / "snapshots"
    run_dir = root / "runs" / day
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    (snapshots_dir / f"{day}.json").write_text(
        json.dumps(snapshot_payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (run_dir / "market_snapshot.json").write_text(
        json.dumps(snapshot_payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (run_dir / "market_intelligence_report.json").write_text(
        json.dumps({**report_payload, "backfill": True}, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (run_dir / "market_intelligence_summary.md").write_text(summary, encoding="utf-8")
    metadata = {
        "as_of": day,
        "started_at": _utc_now(),
        "finished_at": _utc_now(),
        "duration_ms": 0,
        "run_type": HISTORICAL_BACKFILL_RUN_TYPE,
        "backfill": True,
        "live_daily": False,
        "status": "success",
        "warnings": list(dict.fromkeys(warnings)),
        "steps": [
            {
                "step_name": "historical_backfill_market_snapshot",
                "status": "success",
                "output_paths": [str(snapshots_dir / f"{day}.json"), str(run_dir / "market_snapshot.json")],
                "error_message": None,
            }
        ],
    }
    (run_dir / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _build_nav_summary_payload(
    *,
    provider: str,
    start_date: str,
    end_date: str,
    nav_points_by_code: dict[str, list[FundNavPoint]],
    windows: tuple[str, ...],
    warnings: list[str],
) -> dict[str, Any]:
    summaries: dict[str, dict[str, Any]] = {}
    for code, points in sorted(nav_points_by_code.items()):
        summary = build_nav_history_windows_summary(code, points, windows=windows, as_of=end_date)
        metadata = {
            **summary.get("metadata", {}),
            "run_type": HISTORICAL_BACKFILL_RUN_TYPE,
            "backfill": True,
            "provider": provider,
        }
        summaries[code] = {
            **summary,
            "source": f"{provider}:historical_backfill",
            "run_type": HISTORICAL_BACKFILL_RUN_TYPE,
            "backfill": True,
            "metadata": metadata,
        }
    return {
        "schema_version": "1.0",
        "generated_at": _utc_now(),
        "generator": "fund_agent.historical_backfill",
        "run_type": HISTORICAL_BACKFILL_RUN_TYPE,
        "provider": provider,
        "start_date": start_date,
        "end_date": end_date,
        "backfill": True,
        "nav_history_summary": summaries,
        "warnings": list(dict.fromkeys(warnings)),
        "not_production_model": True,
        "main_score_changed": False,
        "main_risk_changed": False,
    }


def _render_backfill_summary(payload: dict[str, Any]) -> str:
    lines = [
        "# Historical Backfill Summary",
        "",
        f"- run_type: {payload['run_type']}",
        f"- provider: {payload['provider']}",
        f"- start_date: {payload['start_date']}",
        f"- end_date: {payload['end_date']}",
        f"- market_snapshot_count: {payload['market_snapshot_count']}",
        f"- nav_summary_count: {payload['nav_summary_count']}",
        "- 回填数据只用于补充历史观察窗口，不会覆盖 daily live 结论。",
        "- 这是研究辅助，不是买卖建议。",
        "- 本阶段不接入主评分/主风险，不改变主报告结论。",
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {item}" for item in payload.get("warnings", [])] or ["- none"])
    return "\n".join(lines) + "\n"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
