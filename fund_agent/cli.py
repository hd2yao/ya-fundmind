from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path

from .agents import run_research
from .cache import FundCache
from .config import (
    load_experiment_scoring_config,
    load_portfolio_config,
    load_provider_config,
    load_watchlist_config,
)
from .contract import ContractValidationSummary, validate_contract_file, validate_output_dir
from .experiment_scoring import (
    compare_experiment_baseline_file,
    explain_experiment_baseline_file,
    explain_experiment_scoring_file,
    run_experiment_config_sensitivity_file,
    run_experiment_scoring_file,
)
from .models import FundRecord, ProviderHealth, ProviderWarning
from .nav_summary import build_nav_history_windows_summary, parse_nav_windows
from .providers import (
    AkshareProvider,
    FixtureProvider,
    ProviderUnavailable,
    TiantianFundProvider,
    load_portfolio_file,
    normalize_fund_code,
)
from .report import render_html, render_markdown, write_json_report
from .signal_candidates import (
    batch_signal_experiment,
    generate_signal_candidates_file,
    write_batch_signal_experiment,
)
from .signal_explanation import explain_signal_candidates_file
from .signal_experiment import evaluate_tiantian_signals_file
from .snapshot import compare_snapshots, load_previous_snapshot, snapshot_from_result, write_snapshot
from .tiantian_diagnostics import build_tiantian_cache_diagnostics, write_tiantian_cache_diagnostics
from .trace import write_provider_trace


DEFAULT_FUNDS_FILE = Path("data/fixtures/funds.json")
DEFAULT_PORTFOLIO_FILE = Path("data/portfolio.example.json")
DEFAULT_WATCHLIST_FILE = Path("configs/watchlist.yaml")
DEFAULT_PORTFOLIO_CONFIG = Path("configs/portfolio.yaml")
DEFAULT_PROVIDER_CONFIG = Path("configs/providers.yaml")
DEFAULT_EXPERIMENT_SCORING_CONFIG = Path("configs/experiment_scoring.yaml")
DEFAULT_CACHE_FILE = Path("data/cache/funds.sqlite")


def _write_reports(result, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "fund_agent_report.md"
    html_path = output_dir / "fund_agent_report.html"
    markdown_path.write_text(render_markdown(result), encoding="utf-8")
    html_path.write_text(render_html(result), encoding="utf-8")
    return markdown_path, html_path


def _load_funds(args, *, as_of: str):
    provider_name = getattr(args, "provider", None)
    provider_config = load_provider_config(args.provider_config).akshare
    provider_verbose = bool(getattr(args, "provider_verbose", False) or provider_config.verbose)
    if provider_name == "akshare":
        cache = FundCache(args.cache_file)
        provider = AkshareProvider(
            cache=cache,
            allow_stale_cache=True,
            verbose=provider_verbose,
            timeout_seconds=provider_config.timeout_seconds,
            retry_count=provider_config.retry_count,
            retry_backoff_seconds=provider_config.retry_backoff_seconds,
        )
        return provider.fetch_funds(as_of=as_of), _provider_health(provider)
    if provider_name == "fixture":
        provider = FixtureProvider(args.funds_file)
        return provider.fetch_funds(as_of=as_of), _provider_health(provider)
    if args.source == "live":
        provider = AkshareProvider(
            verbose=provider_verbose,
            timeout_seconds=provider_config.timeout_seconds,
            retry_count=provider_config.retry_count,
            retry_backoff_seconds=provider_config.retry_backoff_seconds,
        )
        return provider.fetch_funds(as_of=as_of), _provider_health(provider)
    provider = FixtureProvider(args.funds_file)
    return provider.fetch_funds(as_of=as_of), _provider_health(provider)


def _provider_health(provider) -> tuple[ProviderHealth, ...]:
    health = getattr(provider, "last_health", None)
    return (health,) if health is not None else ()


def _filter_watchlist(funds, watchlist_file: Path | None):
    if watchlist_file is None or not watchlist_file.exists():
        return funds
    codes = set(load_watchlist_config(watchlist_file).codes)
    if not codes:
        return funds
    return [fund for fund in funds if fund.code in codes]


def _apply_watchlist_health(
    health_items: tuple[ProviderHealth, ...],
    *,
    all_funds,
    filtered_funds,
    watchlist_file: Path | None,
) -> tuple[ProviderHealth, ...]:
    if not health_items or watchlist_file is None or not watchlist_file.exists():
        return health_items
    requested_codes = tuple(load_watchlist_config(watchlist_file).codes)
    if not requested_codes:
        return health_items
    available_codes = {fund.code for fund in all_funds}
    filtered_codes = {fund.code for fund in filtered_funds}
    missing_codes = tuple(code for code in requested_codes if code not in available_codes)
    matched_count = len(set(requested_codes) & filtered_codes)
    warning = ()
    if missing_codes:
        code = "all_watchlist_missing" if matched_count == 0 else "watchlist_missing"
        severity = "critical" if matched_count == 0 else "warning"
        warning = (
            ProviderWarning(
                code=code,
                message=f"Watchlist codes not found in provider data: {', '.join(missing_codes)}",
                severity=severity,
                details={"missing_codes": list(missing_codes)},
            ),
        )
    return tuple(
        replace(
            health,
            watchlist_requested_count=len(requested_codes),
            watchlist_matched_count=matched_count,
            watchlist_missing_codes=missing_codes,
            warnings=(*health.warnings, *warning),
        )
        for health in health_items
    )


def _run_report(args) -> int:
    as_of = args.as_of or date.today().isoformat()
    provider_config = load_provider_config(args.provider_config)
    try:
        all_funds, provider_health = _load_funds(args, as_of=as_of)
        funds = _filter_watchlist(all_funds, args.watchlist_file)
        provider_health = _apply_watchlist_health(
            provider_health,
            all_funds=all_funds,
            filtered_funds=funds,
            watchlist_file=args.watchlist_file,
        )
    except ProviderUnavailable as exc:
        print(f"Live provider unavailable: {exc}")
        return 2
    except Exception as exc:
        print(f"Failed to load fund data: {exc}")
        return 2

    holdings = None
    if args.portfolio_config and args.portfolio_config.exists():
        holdings = list(load_portfolio_config(args.portfolio_config).holdings)
    elif args.portfolio_file:
        holdings = load_portfolio_file(args.portfolio_file)

    result = run_research(
        funds,
        holdings=holdings,
        as_of=as_of,
        candidate_limit=args.limit,
        provider_health=provider_health,
    )
    previous_snapshot = load_previous_snapshot(args.output_dir, result.as_of)
    snapshot_delta = compare_snapshots(previous_snapshot, snapshot_from_result(result))
    if snapshot_delta:
        result = replace(result, snapshot_delta=snapshot_delta)
    markdown_path, html_path = _write_reports(result, args.output_dir)
    json_path = write_json_report(result, args.output_dir)
    snapshot_path = write_snapshot(result, args.output_dir)
    trace_path = write_provider_trace(
        result,
        args.output_dir,
        retention_days=provider_config.akshare.trace_retention_days,
        max_trace_files=provider_config.akshare.max_trace_files,
    )
    print(f"Markdown report: {markdown_path}")
    print(f"HTML report: {html_path}")
    print(f"JSON report: {json_path}")
    print(f"Snapshot: {snapshot_path}")
    print(f"Provider trace: {trace_path}")
    if _should_fail_exit_policy(result, provider_config.policy):
        print("Data quality exit policy triggered after report generation.")
        return 3
    return 0


def _should_fail_exit_policy(result, policy) -> bool:
    if policy.fail_on_degraded and result.data_quality_grade == "degraded":
        return True
    if policy.fail_on_critical_provider_warning:
        return any(health.has_critical_warnings for health in result.provider_health)
    return False


def _run_smoke_akshare(args) -> int:
    provider_config = load_provider_config(args.provider_config).akshare
    provider = AkshareProvider(
        cache=FundCache(args.cache_file),
        allow_stale_cache=True,
        verbose=bool(getattr(args, "provider_verbose", False) or provider_config.verbose),
        timeout_seconds=provider_config.timeout_seconds,
        retry_count=provider_config.retry_count,
        retry_backoff_seconds=provider_config.retry_backoff_seconds,
    )
    if not getattr(provider, "available", False):
        print("AKShare is not installed; install akshare to run smoke-akshare.")
        return 2
    args.provider = "akshare"
    args.source = "live"
    return _run_report(args)


def _run_validate_contract(args) -> int:
    results = []
    if args.report:
        results.append(validate_contract_file(args.report, "report"))
    if args.trace:
        results.append(validate_contract_file(args.trace, "trace"))
    if args.snapshot:
        results.append(validate_contract_file(args.snapshot, "snapshot"))
    if not results:
        results = list(validate_output_dir(args.output_dir).results)
    summary = ContractValidationSummary(results=tuple(results))
    if not summary.results:
        print("Contract validation failed: no output JSON files found.")
        return 1
    for result in summary.results:
        status = "OK" if result.ok else "FAIL"
        print(f"{status} {result.contract_type}: {result.path}")
        for warning in result.warnings:
            print(f"  warning: {warning}")
        for error in result.errors:
            print(f"  error: {error}")
    return 0 if summary.ok else 1


def _run_enrich_fund(args) -> int:
    if args.provider != "tiantian":
        print(f"Unsupported enrichment provider: {args.provider}")
        return 2
    try:
        nav_windows = parse_nav_windows(args.nav_windows)
    except ValueError as exc:
        print(str(exc))
        return 2
    provider_config = load_provider_config(args.provider_config)
    cache = FundCache(args.cache_file)
    provider = TiantianFundProvider(
        cache=cache,
        timeout_seconds=provider_config.tiantian.timeout_seconds,
        retry_count=provider_config.tiantian.retry_count,
        retry_backoff_seconds=provider_config.tiantian.retry_backoff_seconds,
    )
    if not getattr(provider, "available", False):
        if args.allow_cache:
            return _execute_tiantian_cache_fallback(
                args,
                cache,
                provider_config,
                nav_windows=nav_windows,
                reason="TiantianFundProvider client is not configured",
            )
        print("TiantianFundProvider is not configured; set TIANTIAN_API_BASE_URL to run live enrichment.")
        return 2
    return _execute_tiantian_enrichment(args, provider, provider_config, nav_windows=nav_windows)


def _run_smoke_tiantian(args) -> int:
    provider_config = load_provider_config(args.provider_config)
    try:
        nav_windows = parse_nav_windows(getattr(args, "nav_windows", None))
    except ValueError as exc:
        print(str(exc))
        return 2
    provider = TiantianFundProvider(
        cache=FundCache(args.cache_file),
        timeout_seconds=provider_config.tiantian.timeout_seconds,
        retry_count=provider_config.tiantian.retry_count,
        retry_backoff_seconds=provider_config.tiantian.retry_backoff_seconds,
    )
    if not getattr(provider, "available", False):
        print("TiantianFundProvider is not configured; set TIANTIAN_API_BASE_URL to run real smoke-tiantian.")
        return 2
    return _execute_tiantian_enrichment(args, provider, provider_config, nav_windows=nav_windows)


def _run_diagnose_tiantian_cache(args) -> int:
    cache = FundCache(args.cache_file)
    payload = build_tiantian_cache_diagnostics(cache, code=args.code, as_of=args.as_of or None)
    path = write_tiantian_cache_diagnostics(payload, args.output_dir)
    print(f"Tiantian cache diagnostics: {path}")
    print(
        "detail={detail} nav={nav} nav_points={count} latest_nav_date={latest}".format(
            detail=payload["detail_cache_status"],
            nav=payload["nav_cache_status"],
            count=payload["nav_points_count"],
            latest=payload["latest_nav_date"] or "--",
        )
    )
    if payload["detail_cache_status"] == "miss" or payload["nav_cache_status"] == "miss":
        print(f"Tiantian cache miss for {payload['code']}.")
        return 2
    return 0


def _run_experiment_tiantian_signals(args) -> int:
    path = evaluate_tiantian_signals_file(args.input, args.output)
    print(f"Tiantian signal experiment: {path}")
    return 0


def _run_generate_signal_candidates(args) -> int:
    path = generate_signal_candidates_file(args.input, args.output)
    print(f"Signal candidates: {path}")
    return 0


def _run_batch_signal_experiment(args) -> int:
    result = batch_signal_experiment(input_dir=args.input_dir, snapshot_dir=args.snapshot_dir)
    path = write_batch_signal_experiment(result, args.output)
    print(f"Signal batch report: {path}")
    return 0


def _run_explain_signal_candidates(args) -> int:
    markdown_path, json_path = explain_signal_candidates_file(
        args.input,
        args.output,
        json_output=args.json_output,
    )
    print(f"Signal candidate explanation: {markdown_path}")
    if json_path is not None:
        print(f"Signal candidate explanation JSON: {json_path}")
    return 0


def _run_experiment_scoring(args) -> int:
    config = load_experiment_scoring_config(args.config)
    path = run_experiment_scoring_file(
        report_path=args.report,
        signals_path=args.signals,
        config=config,
        output_path=args.output,
    )
    print(f"Experiment scoring report: {path}")
    return 0


def _run_explain_experiment_scoring(args) -> int:
    path = explain_experiment_scoring_file(args.input, args.output)
    print(f"Experiment scoring explanation: {path}")
    return 0


def _run_compare_experiment_baseline(args) -> int:
    path = compare_experiment_baseline_file(
        report_path=args.report,
        experiment_path=args.experiment,
        output_path=args.output,
    )
    print(f"Experiment baseline comparison: {path}")
    return 0


def _run_explain_experiment_baseline(args) -> int:
    path = explain_experiment_baseline_file(args.input, args.output)
    print(f"Experiment baseline review: {path}")
    return 0


def _run_experiment_config_sensitivity(args) -> int:
    config = load_experiment_scoring_config(args.config)
    path = run_experiment_config_sensitivity_file(
        report_path=args.report,
        signals_path=args.signals,
        config=config,
        output_path=args.output,
    )
    print(f"Experiment config sensitivity: {path}")
    return 0


def _execute_tiantian_enrichment(args, provider, provider_config, *, nav_windows: tuple[str, ...]) -> int:
    as_of = args.as_of or date.today().isoformat()
    try:
        detail = provider.fetch_fund_detail(args.code, as_of=as_of)
        detail_health = provider.last_health
        nav_points = provider.fetch_nav_history(
            args.code,
            start_date=getattr(args, "start_date", None),
            end_date=getattr(args, "end_date", None),
            as_of=as_of,
        )
        nav_health = provider.last_health
    except ProviderUnavailable as exc:
        if getattr(args, "allow_cache", False):
            return _execute_tiantian_cache_fallback(
                args,
                provider.cache,
                provider_config,
                nav_windows=nav_windows,
                reason=str(exc),
            )
        print(f"Tiantian provider unavailable: {exc}")
        return 2
    combined_health = _combine_provider_health(detail_health, nav_health)
    latest_nav = nav_points[-1].unit_nav if nav_points else None
    latest_nav_metadata = nav_points[-1].metadata if nav_points else {}
    fund = FundRecord(
        code=detail.code,
        name=detail.name,
        category=detail.fund_type or "基金",
        nav=latest_nav,
        nav_date=nav_points[-1].date if nav_points else None,
        source=detail.source,
        metadata={
            **detail.metadata,
            "updated_at": latest_nav_metadata.get("updated_at", detail.metadata.get("updated_at")),
            "expires_at": latest_nav_metadata.get("expires_at", detail.metadata.get("expires_at")),
            "stale": bool(detail.metadata.get("stale") or latest_nav_metadata.get("stale")),
        },
    )
    result = run_research(
        [fund],
        as_of=as_of,
        provider_health=(combined_health,) if combined_health is not None else (),
    )
    nav_summary = {
        detail.code: build_nav_history_windows_summary(
            detail.code,
            nav_points,
            windows=nav_windows,
            as_of=as_of,
        )
    }
    if combined_health is not None:
        combined_health = _with_window_health(combined_health, nav_summary[detail.code])
        result = replace(result, provider_health=(combined_health,))
    result = replace(result, fund_details=(detail,), nav_history_summary=nav_summary)
    json_path = write_json_report(result, args.output_dir)
    trace_path = write_provider_trace(
        result,
        args.output_dir,
        retention_days=provider_config.tiantian.trace_retention_days,
        max_trace_files=provider_config.tiantian.max_trace_files,
    )
    print(f"JSON report: {json_path}")
    print(f"Provider trace: {trace_path}")
    print(f"Tiantian detail: {detail.code} {detail.name}")
    print(f"Tiantian nav rows: {len(nav_points)}")
    print(f"Tiantian detail cache writes: {1 if detail else 0}")
    print(f"Tiantian nav cache writes: {len(nav_points)}")
    contract_summary = validate_output_dir(args.output_dir)
    print(f"Contract validation: {'OK' if contract_summary.ok else 'FAIL'}")
    return 0


def _execute_tiantian_cache_fallback(args, cache: FundCache, provider_config, *, nav_windows: tuple[str, ...], reason: str) -> int:
    as_of = args.as_of or date.today().isoformat()
    code = normalize_fund_code(args.code)
    details = [
        item for item in cache.load_fund_details(code=code, as_of=as_of, allow_stale=True)
        if item.source == "cache:tiantian"
    ]
    if not details:
        details = [
            item for item in cache.load_fund_details(code=code, allow_stale=True)
            if item.source == "cache:tiantian"
        ]
    nav_points = [
        item for item in cache.load_nav_points(
            code=code,
            start_date=getattr(args, "start_date", None),
            end_date=getattr(args, "end_date", None),
            allow_stale=True,
        )
        if item.source == "cache:tiantian"
    ]
    if not details or not nav_points:
        print(f"Tiantian cache fallback missed for {code}; no cached fund detail or nav history.")
        return 2
    detail = details[-1]
    stale_items = [
        item for item in (*details, *nav_points)
        if item.metadata.get("stale")
    ]
    warnings = [
        ProviderWarning(
            code="live_fallback",
            message=f"Tiantian live unavailable; using cache. reason={reason}",
            severity="warning",
        )
    ]
    if stale_items:
        warnings.append(
            ProviderWarning(
                code="stale_cache",
                message=f"Tiantian cache fallback used {len(stale_items)} stale records.",
                severity="warning",
            )
        )
    nav_summary = {
        detail.code: build_nav_history_windows_summary(
            detail.code,
            nav_points,
            windows=nav_windows,
            as_of=as_of,
        )
    }
    health = ProviderHealth(
        provider="tiantian",
        provider_version=None,
        started_at=_utc_now_iso(),
        finished_at=_utc_now_iso(),
        duration_ms=0,
        mapped_row_count=1 + len(nav_points),
        cache_read_count=1 + len(nav_points),
        fallback_used=True,
        fallback_reason=reason,
        fallback_source="cache:tiantian",
        warnings=tuple(warnings),
        metadata={
            "windows_requested": list(nav_windows),
            "windows_generated": list(nav_summary[detail.code]["windows"].keys()),
        },
    )
    latest_nav = nav_points[-1].unit_nav if nav_points else None
    fund = FundRecord(
        code=detail.code,
        name=detail.name,
        category=detail.fund_type or "基金",
        nav=latest_nav,
        nav_date=nav_points[-1].date if nav_points else None,
        source=detail.source,
    )
    result = run_research([fund], as_of=as_of, provider_health=(health,))
    result = replace(result, fund_details=(detail,), nav_history_summary=nav_summary)
    json_path = write_json_report(result, args.output_dir)
    trace_path = write_provider_trace(
        result,
        args.output_dir,
        retention_days=provider_config.tiantian.trace_retention_days,
        max_trace_files=provider_config.tiantian.max_trace_files,
    )
    print(f"JSON report: {json_path}")
    print(f"Provider trace: {trace_path}")
    print(f"Tiantian cache fallback: {detail.code} {detail.name}")
    print(f"Tiantian cache reads: {health.cache_read_count}")
    contract_summary = validate_output_dir(args.output_dir)
    print(f"Contract validation: {'OK' if contract_summary.ok else 'FAIL'}")
    return 0


def _combine_provider_health(*items):
    health_items = [item for item in items if item is not None]
    if not health_items:
        return None
    first = health_items[0]
    last = health_items[-1]
    return replace(
        last,
        started_at=first.started_at,
        live_row_count=sum(item.live_row_count for item in health_items),
        mapped_row_count=sum(item.mapped_row_count for item in health_items),
        skipped_row_count=sum(item.skipped_row_count for item in health_items),
        cache_read_count=sum(item.cache_read_count for item in health_items),
        cache_write_count=sum(item.cache_write_count for item in health_items),
        endpoints=tuple(endpoint for item in health_items for endpoint in item.endpoints),
        warnings=tuple(warning for item in health_items for warning in item.warnings),
        metadata={key: value for item in health_items for key, value in item.metadata.items()},
    )


def _with_window_health(health: ProviderHealth, summary: dict) -> ProviderHealth:
    return replace(
        health,
        metadata={
            **health.metadata,
            "windows_requested": list(summary.get("windows_requested", [])),
            "windows_generated": list(summary.get("windows", {}).keys()),
        },
    )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fund-agent",
        description="YA FundMind 基金智研系统。输出仅用于研究辅助，不构成投资建议。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_report_args(
        command_parser: argparse.ArgumentParser,
        *,
        include_portfolio: bool,
        default_watchlist: Path | None = None,
        default_portfolio_config: Path | None = None,
        default_provider: str | None = None,
    ) -> None:
        command_parser.add_argument("--source", choices=["fixture", "live"], default="fixture")
        command_parser.add_argument(
            "--provider",
            choices=["fixture", "akshare"],
            default=default_provider,
            help="数据 provider。daily 推荐使用 akshare；旧命令未指定时沿用 --source。",
        )
        command_parser.add_argument("--funds-file", type=Path, default=DEFAULT_FUNDS_FILE)
        command_parser.add_argument("--watchlist-file", type=Path, default=default_watchlist)
        command_parser.add_argument("--cache-file", type=Path, default=DEFAULT_CACHE_FILE)
        command_parser.add_argument("--provider-config", type=Path, default=DEFAULT_PROVIDER_CONFIG)
        command_parser.add_argument(
            "--portfolio-file",
            type=Path,
            default=DEFAULT_PORTFOLIO_FILE if include_portfolio else None,
        )
        command_parser.add_argument("--portfolio-config", type=Path, default=default_portfolio_config)
        command_parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
        command_parser.add_argument("--as-of", default="")
        command_parser.add_argument("--limit", type=int, default=5)
        command_parser.add_argument(
            "--provider-verbose",
            action="store_true",
            help="显示 provider 底层库输出，用于调试 live 数据源。",
        )

    demo = subparsers.add_parser("demo", help="使用内置样例数据生成报告")
    add_report_args(demo, include_portfolio=True)
    demo.set_defaults(func=_run_report)

    screen = subparsers.add_parser("screen", help="只做基金/ETF 研究优先级筛选")
    add_report_args(screen, include_portfolio=False, default_watchlist=DEFAULT_WATCHLIST_FILE)
    screen.set_defaults(func=_run_report)

    portfolio = subparsers.add_parser("portfolio", help="分析本地基金/ETF 持仓")
    add_report_args(
        portfolio,
        include_portfolio=True,
        default_watchlist=DEFAULT_WATCHLIST_FILE,
        default_portfolio_config=DEFAULT_PORTFOLIO_CONFIG,
    )
    portfolio.set_defaults(func=_run_report)

    daily = subparsers.add_parser("daily", help="按配置生成每日基金/持仓研究报告")
    add_report_args(
        daily,
        include_portfolio=True,
        default_watchlist=DEFAULT_WATCHLIST_FILE,
        default_portfolio_config=DEFAULT_PORTFOLIO_CONFIG,
        default_provider="fixture",
    )
    daily.set_defaults(func=_run_report)

    smoke = subparsers.add_parser("smoke-akshare", help="可选：使用 AKShare 真实数据跑 live smoke")
    add_report_args(
        smoke,
        include_portfolio=True,
        default_watchlist=DEFAULT_WATCHLIST_FILE,
        default_portfolio_config=DEFAULT_PORTFOLIO_CONFIG,
        default_provider="akshare",
    )
    smoke.set_defaults(func=_run_smoke_akshare)

    validate = subparsers.add_parser("validate-contract", help="校验 JSON report/trace/snapshot 输出契约")
    validate.add_argument("--output-dir", type=Path, default=Path("outputs"))
    validate.add_argument("--report", type=Path)
    validate.add_argument("--trace", type=Path)
    validate.add_argument("--snapshot", type=Path)
    validate.set_defaults(func=_run_validate_contract)

    enrich = subparsers.add_parser("enrich-fund", help="显式补充单只基金详情和历史净值")
    enrich.add_argument("--provider", choices=["tiantian"], required=True)
    enrich.add_argument("--code", required=True)
    enrich.add_argument("--start-date")
    enrich.add_argument("--end-date")
    enrich.add_argument("--cache-file", type=Path, default=DEFAULT_CACHE_FILE)
    enrich.add_argument("--provider-config", type=Path, default=DEFAULT_PROVIDER_CONFIG)
    enrich.add_argument("--output-dir", type=Path, default=Path("outputs"))
    enrich.add_argument("--as-of", default="")
    enrich.add_argument("--nav-windows", default="1m,3m,6m")
    enrich.add_argument("--allow-cache", action="store_true")
    enrich.set_defaults(func=_run_enrich_fund)

    smoke_tiantian = subparsers.add_parser("smoke-tiantian", help="可选：使用 Tiantian 真实数据跑 live smoke")
    smoke_tiantian.add_argument("--code", required=True)
    smoke_tiantian.add_argument("--start-date")
    smoke_tiantian.add_argument("--end-date")
    smoke_tiantian.add_argument("--cache-file", type=Path, default=DEFAULT_CACHE_FILE)
    smoke_tiantian.add_argument("--provider-config", type=Path, default=DEFAULT_PROVIDER_CONFIG)
    smoke_tiantian.add_argument("--output-dir", type=Path, default=Path("outputs"))
    smoke_tiantian.add_argument("--as-of", default="")
    smoke_tiantian.add_argument("--nav-windows", default="1m,3m,6m")
    smoke_tiantian.set_defaults(func=_run_smoke_tiantian)

    diagnose_cache = subparsers.add_parser("diagnose-tiantian-cache", help="只读本地 cache，诊断 Tiantian enrichment fallback 可用性")
    diagnose_cache.add_argument("--code", required=True)
    diagnose_cache.add_argument("--cache-file", type=Path, default=DEFAULT_CACHE_FILE)
    diagnose_cache.add_argument("--output-dir", type=Path, default=Path("outputs"))
    diagnose_cache.add_argument("--as-of", default="")
    diagnose_cache.set_defaults(func=_run_diagnose_tiantian_cache)

    experiment = subparsers.add_parser("experiment-tiantian-signals", help="评估 Tiantian 字段未来进入评分/风险的候选资格")
    experiment.add_argument("--input", type=Path, required=True)
    experiment.add_argument("--output", type=Path, default=Path("outputs/tiantian_signal_experiment.json"))
    experiment.set_defaults(func=_run_experiment_tiantian_signals)

    signals = subparsers.add_parser("generate-signal-candidates", help="生成投研信号候选层 JSON，不修改主评分/风险")
    signals.add_argument("--input", type=Path, required=True)
    signals.add_argument("--output", type=Path, default=Path("outputs/signal_candidates.json"))
    signals.set_defaults(func=_run_generate_signal_candidates)

    batch = subparsers.add_parser("batch-signal-experiment", help="批量统计 signal candidate JSON 或 report/snapshot JSON")
    batch.add_argument("--input-dir", type=Path)
    batch.add_argument("--snapshot-dir", type=Path)
    batch.add_argument("--output", type=Path, default=Path("outputs/signal_batch_report.json"))
    batch.set_defaults(func=_run_batch_signal_experiment)

    explain = subparsers.add_parser("explain-signal-candidates", help="生成候选信号解释报告，不修改主评分/风险")
    explain.add_argument("--input", type=Path, required=True)
    explain.add_argument("--output", type=Path, default=Path("outputs/signal_candidates_explained.md"))
    explain.add_argument("--json-output", type=Path)
    explain.set_defaults(func=_run_explain_signal_candidates)

    exp_score = subparsers.add_parser("experiment-scoring", help="独立实验评分/风险沙箱，不修改主评分/风险")
    exp_score.add_argument("--report", type=Path, required=True)
    exp_score.add_argument("--signals", type=Path, required=True)
    exp_score.add_argument("--config", type=Path, default=DEFAULT_EXPERIMENT_SCORING_CONFIG)
    exp_score.add_argument("--output", type=Path, default=Path("outputs/experiment_scoring_report.json"))
    exp_score.set_defaults(func=_run_experiment_scoring)

    exp_explain = subparsers.add_parser("explain-experiment-scoring", help="解释实验评分/风险沙箱输出")
    exp_explain.add_argument("--input", type=Path, required=True)
    exp_explain.add_argument("--output", type=Path, default=Path("outputs/experiment_scoring_explained.md"))
    exp_explain.set_defaults(func=_run_explain_experiment_scoring)

    exp_compare = subparsers.add_parser("compare-experiment-baseline", help="对照主分数和实验分数，不修改主报告")
    exp_compare.add_argument("--report", type=Path, required=True)
    exp_compare.add_argument("--experiment", type=Path, required=True)
    exp_compare.add_argument("--output", type=Path, default=Path("outputs/experiment_baseline_comparison.json"))
    exp_compare.set_defaults(func=_run_compare_experiment_baseline)

    exp_baseline_explain = subparsers.add_parser("explain-experiment-baseline", help="生成实验基线人工审核 Markdown")
    exp_baseline_explain.add_argument("--input", type=Path, required=True)
    exp_baseline_explain.add_argument("--output", type=Path, default=Path("outputs/experiment_baseline_review.md"))
    exp_baseline_explain.set_defaults(func=_run_explain_experiment_baseline)

    exp_sensitivity = subparsers.add_parser("experiment-config-sensitivity", help="轻量检查实验评分配置敏感性")
    exp_sensitivity.add_argument("--report", type=Path, required=True)
    exp_sensitivity.add_argument("--signals", type=Path, required=True)
    exp_sensitivity.add_argument("--config", type=Path, default=DEFAULT_EXPERIMENT_SCORING_CONFIG)
    exp_sensitivity.add_argument("--output", type=Path, default=Path("outputs/experiment_config_sensitivity.json"))
    exp_sensitivity.set_defaults(func=_run_experiment_config_sensitivity)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
