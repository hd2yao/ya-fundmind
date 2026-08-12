from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from dataclasses import asdict, replace
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from .agents import run_research
from .cache import FundCache
from .config import (
    load_experiment_scoring_config,
    load_portfolio_config,
    load_provider_config,
    load_research_loop_config,
    load_watchlist_config,
)
from .contract import ContractValidationSummary, validate_contract_file, validate_output_dir
from .evidence_dashboard import generate_evidence_dashboard
from .experiment_scoring import (
    compare_experiment_baseline_file,
    explain_experiment_baseline_file,
    explain_experiment_scoring_file,
    run_experiment_config_sensitivity_file,
    run_experiment_scoring_file,
)
from .fund_detail import (
    build_fund_detail_views,
    write_single_fund_detail,
    write_watchlist_fund_details,
)
from .fund_profile import (
    FundProfileService,
    FundProfileUnavailable,
    write_fund_profile_artifact,
)
from .historical_backfill import run_historical_backfill
from .long_horizon import evaluate_long_horizon_stability, write_long_horizon_stability
from .market_history import MarketHistoryService
from .market_intelligence import (
    build_market_intelligence_report,
    build_market_trend_report,
    fund_record_to_market_record,
    write_market_intelligence_outputs,
    write_market_trend_outputs,
)
from .mcp_server import McpDependencyUnavailable, run_mcp_server
from .models import FundRecord, ProviderHealth, ProviderWarning
from .nav_summary import build_nav_history_windows_summary, parse_nav_windows
from .news_evidence import collect_news_evidence
from .ops import build_ops_status, write_latest_summary, write_ops_status
from .portfolio_analysis import build_portfolio_analysis_report, write_portfolio_analysis_outputs
from .providers import (
    AkshareProvider,
    FixtureProvider,
    ProviderUnavailable,
    TiantianFundProvider,
    load_portfolio_file,
    normalize_fund_code,
)
from .report import render_html, render_markdown, write_json_report
from .release_readiness import evaluate_release_readiness, write_release_readiness
from .research_evidence import build_evidence_bundle
from .research_copilot import ResearchCopilot
from .research_output import write_research_answer_outputs
from .sector_history import MarketSectorService
from .research_loop import (
    execute_research_step,
    run_weekly_research,
    write_daily_research_summary,
    write_run_bundle,
)
from .research_query import ResearchQueryService, SUPPORTED_RESEARCH_TOPICS
from .review_state import list_review_state, summarize_review_state, update_review_state
from .runtime_provenance import collect_runtime_provenance
from .signal_candidates import (
    batch_signal_experiment,
    generate_signal_candidates_file,
    write_batch_signal_experiment,
)
from .signal_explanation import explain_signal_candidates_file
from .signal_experiment import evaluate_tiantian_signals_file
from .signal_review import (
    generate_signal_promotion_proposal_file,
    review_signal_readiness_file,
)
from .snapshot import compare_snapshots, load_previous_snapshot, snapshot_from_result, write_snapshot
from .tiantian_diagnostics import build_tiantian_cache_diagnostics, write_tiantian_cache_diagnostics
from .trace import write_provider_health_trace, write_provider_trace
from .web_console import build_web_console_state


DEFAULT_FUNDS_FILE = Path("data/fixtures/funds.json")
DEFAULT_PORTFOLIO_FILE = Path("data/portfolio.example.json")
DEFAULT_WATCHLIST_FILE = Path("configs/watchlist.yaml")
DEFAULT_PORTFOLIO_CONFIG = Path("configs/portfolio.yaml")
DEFAULT_PROVIDER_CONFIG = Path("configs/providers.yaml")
DEFAULT_EXPERIMENT_SCORING_CONFIG = Path("configs/experiment_scoring.yaml")
DEFAULT_SIGNAL_THRESHOLD_CONFIG = Path("configs/signal_threshold_candidates.yaml")
DEFAULT_RESEARCH_LOOP_CONFIG = Path("configs/research_loop.yaml")
DEFAULT_REVIEW_STATE_FILE = Path("outputs/manual_review_state.json")
DEFAULT_CACHE_FILE = Path("data/cache/funds.sqlite")
DEFAULT_MARKET_THEMES_CONFIG = Path("configs/market_themes.yaml")
DEFAULT_NEWS_EVIDENCE_FILE = Path("data/fixtures/news_evidence.json")


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
    if args.research_context:
        results.append(validate_contract_file(args.research_context, "research_context"))
    if args.evidence_bundle:
        results.append(validate_contract_file(args.evidence_bundle, "evidence_bundle"))
    if args.research_answer:
        results.append(validate_contract_file(args.research_answer, "research_answer"))
    if args.mcp_result:
        results.append(validate_contract_file(args.mcp_result, "mcp_tool_result"))
    if args.release_readiness:
        results.append(validate_contract_file(args.release_readiness, "release_readiness"))
    if args.fund_profile:
        results.append(validate_contract_file(args.fund_profile, "fund_profile"))
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


def _run_release_readiness(args) -> int:
    result = evaluate_release_readiness(
        args.output_dir,
        minimum_valid_runs=args.minimum_valid_runs,
        release_target=args.release_target,
        observation_mode=args.observation_mode,
        required_app_version=args.required_app_version,
        required_git_commit=args.required_git_commit,
    )
    output = args.json_output or args.output_dir / "release" / "v2_release_readiness.json"
    write_release_readiness(result, output)
    print(f"Release readiness: {output}")
    print(
        "Release gate: mode={mode} status={status} valid_runs={valid}/{minimum} "
        "contracts={contracts} performance={performance}".format(
            mode=result["observation_mode"],
            status=result["status"],
            valid=result["valid_run_count"],
            minimum=result["minimum_valid_runs"],
            contracts=result["contract_summary"]["ok"],
            performance=result["performance"]["within_budget"],
        )
    )
    for blocker in result["blockers"]:
        print(f"  blocker: {blocker}")
    return 0 if result["status"] == "pass" else 1


def _run_research_query(args) -> int:
    code = args.code
    if code is not None:
        if args.topic != "fund":
            print("--code is only supported for --topic fund")
            return 2
        code = normalize_fund_code(code)
        if len(code) != 6 or not code.isdigit():
            print(f"Invalid fund code: {args.code}")
            return 2
    context = ResearchQueryService(args.output_dir).query(args.topic, code=code)
    output = args.output or args.output_dir / "research_queries" / "research_context.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(asdict(context), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"Research context: {output}")
    print(f"Research query: topic={context.topic} status={context.status} as_of={context.as_of or '--'}")
    return 1 if context.status == "unavailable" else 0


def _run_build_research_evidence(args) -> int:
    context_path = args.context or args.output_dir / "research_queries" / "research_context.json"
    validation = validate_contract_file(context_path, "research_context")
    if not validation.ok:
        print(f"Invalid research context: {context_path}")
        for error in validation.errors:
            print(f"  error: {error}")
        return 2
    payload = json.loads(context_path.read_text(encoding="utf-8"))
    bundle = build_evidence_bundle(payload, args.output_dir)
    output = args.output or args.output_dir / "evidence" / "research_evidence.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(asdict(bundle), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"Research evidence: {output}")
    print(
        "Evidence bundle: "
        f"topic={bundle.topic} status={bundle.status} quality={bundle.quality_grade} "
        f"findings={len(bundle.findings)} evidence={len(bundle.evidence)}"
    )
    return 1 if bundle.status == "unavailable" else 0


def _run_research_ask(args) -> int:
    answer = ResearchCopilot(args.output_dir).answer(args.question)
    outputs = write_research_answer_outputs(
        answer,
        args.output_dir,
        json_path=args.output,
        markdown_path=args.markdown_output,
        audit_path=args.audit_output,
    )
    print(f"Research answer: {outputs.json_path}")
    print(f"Research answer Markdown: {outputs.markdown_path}")
    print(f"Research audit: {outputs.audit_path}")
    print(
        "Research ask: "
        f"intent={answer.intent.get('intent')} status={answer.answer_status} "
        f"findings={len(answer.findings)} evidence={len(answer.evidence)}"
    )
    return 0 if answer.answer_status in {"answered", "partial"} else 1


def _run_mcp_server(args) -> int:
    try:
        result = run_mcp_server(
            args.output_dir,
            transport=args.transport,
            timeout_seconds=args.timeout_seconds,
            audit_path=args.audit_output,
            dry_run=args.dry_run,
        )
    except McpDependencyUnavailable as exc:
        print(f"MCP server unavailable: {exc}")
        return 2
    except ValueError as exc:
        print(f"Invalid MCP server configuration: {exc}")
        return 2
    if args.dry_run:
        print(
            "MCP server ready: "
            f"transport={result['transport']} tools={', '.join(result['tools'])} read_only=true"
        )
    return 0


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
    reference_time = None
    if args.as_of:
        reference_time = datetime.fromisoformat(args.as_of).replace(tzinfo=timezone.utc)
    payload = build_tiantian_cache_diagnostics(
        cache,
        code=args.code,
        as_of=args.as_of or None,
        now=reference_time,
    )
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


def _run_review_signal_readiness(args) -> int:
    path = review_signal_readiness_file(
        signals_path=args.signals,
        stability_path=args.stability,
        baseline_path=args.baseline,
        sensitivity_path=args.sensitivity,
        thresholds_path=args.thresholds,
        output_path=args.output,
    )
    print(f"Signal readiness review: {path}")
    print(f"Manual review queue: {path.parent / 'manual_review_queue.json'}")
    return 0


def _run_generate_signal_promotion_proposal(args) -> int:
    path = generate_signal_promotion_proposal_file(
        review_path=args.review,
        output_path=args.output,
    )
    print(f"Signal promotion proposal: {path}")
    return 0


def _run_market_scan(args) -> int:
    as_of = args.as_of or date.today().isoformat()
    try:
        funds = _load_market_scan_funds(args, as_of=as_of)
    except ProviderUnavailable as exc:
        print(f"No market fund data available: {exc}")
        return 2
    except Exception as exc:
        print(f"Market scan failed: {exc}")
        return 2
    if not funds:
        print("No market fund data available from provider or cache.")
        return 2
    records = [fund_record_to_market_record(fund, as_of=as_of) for fund in funds]
    report = build_market_intelligence_report(
        records,
        as_of=as_of,
        source=args.provider,
        themes_config=args.themes_config,
        top_n=args.top_n,
        min_theme_sample_size=args.min_theme_sample_size,
    )
    outputs = write_market_intelligence_outputs(report, args.output_dir)
    print(f"Market intelligence report: {outputs.report_path}")
    print(f"Market intelligence summary: {outputs.summary_path}")
    print(f"Market theme rankings: {outputs.theme_rankings_path}")
    print(f"Market fund candidates: {outputs.fund_candidates_path}")
    print(f"Market snapshot: {outputs.snapshot_path}")
    print(f"Run bundle market report: {outputs.run_report_path}")
    return 0


def _build_cli_market_history_service(args) -> MarketHistoryService:
    cache = FundCache(args.cache_file)
    provider_config = load_provider_config(args.provider_config).akshare
    provider = AkshareProvider(
        cache=cache,
        allow_stale_cache=True,
        verbose=bool(getattr(args, "provider_verbose", False) or provider_config.verbose),
        timeout_seconds=provider_config.timeout_seconds,
        retry_count=provider_config.retry_count,
        retry_backoff_seconds=provider_config.retry_backoff_seconds,
    )
    return MarketHistoryService(
        cache=cache,
        provider=provider,
        cache_ttl_days=1,
        allow_stale_fallback=True,
    )


def _build_cli_market_sector_service(args) -> MarketSectorService:
    cache = FundCache(args.cache_file)
    provider_config = load_provider_config(args.provider_config).akshare
    provider = AkshareProvider(
        cache=cache,
        allow_stale_cache=True,
        verbose=bool(
            getattr(args, "provider_verbose", False)
            or provider_config.verbose
        ),
        timeout_seconds=provider_config.timeout_seconds,
        retry_count=provider_config.retry_count,
        retry_backoff_seconds=provider_config.retry_backoff_seconds,
    )
    return MarketSectorService(
        cache=cache,
        provider=provider,
        cache_ttl_days=1,
        allow_stale_fallback=True,
    )


def _parse_refresh_as_of(as_of: str) -> str | None:
    if not as_of:
        return None
    try:
        return date.fromisoformat(as_of).isoformat()
    except ValueError as exc:
        raise ValueError("--as-of must be an ISO date, for example 2026-07-27.") from exc


def _build_fund_profile_runtime(args):
    provider_config = load_provider_config(args.provider_config).akshare
    cache = FundCache(args.cache_file)
    provider = AkshareProvider(
        cache=cache,
        cache_ttl_days=int(getattr(args, "profile_cache_ttl_days", 7)),
        verbose=bool(getattr(args, "provider_verbose", False) or provider_config.verbose),
        timeout_seconds=provider_config.timeout_seconds,
        retry_count=provider_config.retry_count,
        retry_backoff_seconds=provider_config.retry_backoff_seconds,
    )
    return cache, provider, provider_config


def _health_with_cache_writes(health, count: int):
    if not isinstance(health, ProviderHealth):
        return None
    return replace(
        health,
        cache_write_count=health.cache_write_count + count,
    )


def _run_refresh_fund_profile_reference(args) -> int:
    if args.reference_ttl_days < 1:
        print("--reference-ttl-days must be at least 1")
        return 2
    if args.minimum_entry_count < 1:
        print("--minimum-entry-count must be at least 1")
        return 2
    if not 0 <= args.catalog_minimum_mapped_ratio <= 1:
        print("--catalog-minimum-mapped-ratio must be between 0 and 1")
        return 2
    if not 0 <= args.purchase_minimum_mapped_ratio <= 1:
        print("--purchase-minimum-mapped-ratio must be between 0 and 1")
        return 2
    try:
        as_of = _parse_refresh_as_of(args.as_of) or date.today().isoformat()
        cache, provider, provider_config = _build_fund_profile_runtime(args)
    except (OSError, ValueError) as exc:
        print(f"Fund profile reference refresh failed: {exc}")
        return 2
    if not getattr(provider, "available", True):
        print("AKShare is not installed; fund profile reference refresh is unavailable.")
        return 2

    generated_at = datetime.now(timezone.utc)
    provider_health: list[ProviderHealth] = []
    components: dict[str, dict] = {}

    try:
        catalog = provider.fetch_fund_catalog(as_of=as_of)
        catalog_health = getattr(provider, "last_health", None)
        cache.replace_fund_catalog_snapshot(
            catalog,
            snapshot_id=f"catalog-{as_of}-{uuid4().hex}",
            as_of=as_of,
            ttl_days=args.reference_ttl_days,
            minimum_entry_count=args.minimum_entry_count,
            raw_entry_count=(catalog_health.live_row_count if catalog_health else None),
            minimum_mapped_ratio=args.catalog_minimum_mapped_ratio,
            now=generated_at,
            metadata={"refresh_command": "refresh-fund-profile-reference"},
        )
    except (ProviderUnavailable, ValueError, OSError) as exc:
        catalog_health = getattr(provider, "last_health", None)
        components["catalog"] = {
            "status": "failed",
            "entry_count": 0,
            "error": str(exc),
        }
    else:
        catalog_health = _health_with_cache_writes(catalog_health, len(catalog))
        components["catalog"] = {
            "status": "success",
            "entry_count": len(catalog),
            "raw_entry_count": catalog_health.live_row_count if catalog_health else None,
        }
    if isinstance(catalog_health, ProviderHealth):
        provider_health.append(catalog_health)

    try:
        purchase_rules = provider.fetch_purchase_statuses(as_of=as_of)
        purchase_health = getattr(provider, "last_health", None)
        cache.replace_purchase_snapshot(
            purchase_rules,
            snapshot_id=f"purchase-{as_of}-{uuid4().hex}",
            as_of=as_of,
            ttl_days=args.reference_ttl_days,
            minimum_entry_count=args.minimum_entry_count,
            raw_entry_count=(purchase_health.live_row_count if purchase_health else None),
            minimum_mapped_ratio=args.purchase_minimum_mapped_ratio,
            now=generated_at,
            metadata={"refresh_command": "refresh-fund-profile-reference"},
        )
    except (ProviderUnavailable, ValueError, OSError) as exc:
        purchase_health = getattr(provider, "last_health", None)
        components["purchase"] = {
            "status": "failed",
            "entry_count": 0,
            "error": str(exc),
        }
    else:
        purchase_health = _health_with_cache_writes(
            purchase_health,
            len(purchase_rules),
        )
        components["purchase"] = {
            "status": "success",
            "entry_count": len(purchase_rules),
            "raw_entry_count": purchase_health.live_row_count if purchase_health else None,
        }
    if isinstance(purchase_health, ProviderHealth):
        provider_health.append(purchase_health)

    success_count = sum(item["status"] == "success" for item in components.values())
    status = "success" if success_count == 2 else "partial" if success_count else "unavailable"
    trace_path = write_provider_health_trace(
        as_of=as_of,
        provider_health=tuple(provider_health),
        output_dir=args.output_dir,
        filename_prefix="provider-fund-profile-reference",
        retention_days=provider_config.trace_retention_days,
        max_trace_files=provider_config.max_trace_files,
        now=generated_at,
    )
    report = {
        "schema_version": "1.0",
        "generated_at": generated_at.isoformat(),
        "generator": "fund_agent",
        "as_of": as_of,
        "status": status,
        **components,
        "provider_trace": str(trace_path.relative_to(args.output_dir)),
        "boundaries": {
            "legacy_fund_basics_written": False,
            "legacy_fund_details_written": False,
            "daily_scheduler_changed": False,
            "main_score_changed": False,
            "main_risk_changed": False,
        },
    }
    report_path = args.output_dir / "fund_profiles" / "reference_refresh_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Fund profile reference report: {report_path}")
    print(f"Provider trace: {trace_path}")
    print(
        "Fund profile reference refresh: "
        f"status={status} catalog={components['catalog']['status']} "
        f"purchase={components['purchase']['status']}"
    )
    return 0 if status == "success" else 2


def _run_fetch_fund_profile(args) -> int:
    code = normalize_fund_code(args.code)
    if len(code) != 6 or not code.isdigit():
        print("fetch-fund-profile requires a six-digit fund code")
        return 2
    if args.profile_cache_ttl_days < 1:
        print("--profile-cache-ttl-days must be at least 1")
        return 2
    try:
        as_of = _parse_refresh_as_of(args.as_of) or date.today().isoformat()
        cache, provider, provider_config = _build_fund_profile_runtime(args)
    except (OSError, ValueError) as exc:
        print(f"Fund profile fetch failed: {exc}")
        return 2
    if not getattr(provider, "available", True):
        print("AKShare is not installed; fund profile fetch is unavailable.")
        return 2

    generated_at = datetime.now(timezone.utc)
    service = FundProfileService(
        cache=cache,
        provider=provider,
        cache_ttl_days=args.profile_cache_ttl_days,
    )
    try:
        bundle = service.get_profile(code, as_of=as_of, now=generated_at)
    except (FundProfileUnavailable, ProviderUnavailable, ValueError) as exc:
        trace_path = write_provider_health_trace(
            as_of=as_of,
            provider_health=service.last_provider_health,
            output_dir=args.output_dir,
            filename_prefix=f"provider-fund-profile-{code}",
            retention_days=provider_config.trace_retention_days,
            max_trace_files=provider_config.max_trace_files,
            now=generated_at,
        )
        print(f"Fund profile fetch failed: {exc}")
        print(f"Provider trace: {trace_path}")
        return 2

    artifact_path = write_fund_profile_artifact(
        bundle,
        args.output_dir,
        as_of=as_of,
        generated_at=generated_at,
    )
    trace_path = write_provider_health_trace(
        as_of=as_of,
        provider_health=service.last_provider_health,
        output_dir=args.output_dir,
        filename_prefix=f"provider-fund-profile-{code}",
        retention_days=provider_config.trace_retention_days,
        max_trace_files=provider_config.max_trace_files,
        now=generated_at,
    )
    validation = validate_contract_file(artifact_path, "fund_profile", strict=True)
    print(f"Fund profile artifact: {artifact_path}")
    print(f"Provider trace: {trace_path}")
    print(f"Fund profile status: {bundle.data_status}")
    if not validation.ok:
        for error in validation.errors:
            print(f"  contract error: {error}")
        return 2
    return 0


def _parse_market_sector_symbols(value: str) -> list[str]:
    symbols: list[str] = []
    seen: set[str] = set()
    for raw in value.split(","):
        symbol = raw.strip().upper()
        if not symbol:
            continue
        if not re.fullmatch(r"BK\d{4}", symbol):
            raise ValueError(
                "--symbols must be a comma-separated list of BK codes, "
                "for example BK1042,BK1036."
            )
        if symbol not in seen:
            seen.add(symbol)
            symbols.append(symbol)
    if not symbols:
        raise ValueError("--symbols requires at least one BK code.")
    return symbols


def _run_refresh_market_history(args) -> int:
    if args.provider != "akshare":
        print("refresh-market-history requires --provider akshare; fixture data is not refreshed.")
        return 2
    try:
        payload = _build_cli_market_history_service(args).refresh_index_histories(
            now=datetime.now(timezone.utc),
            as_of=_parse_refresh_as_of(args.as_of),
        )
    except ValueError as exc:
        print(str(exc))
        return 2
    except Exception as exc:
        print(f"Market history refresh failed: {exc}")
        return 2

    output_path = args.output_dir / "market" / "index_refresh_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Market index refresh report: {output_path}")
    print(
        "Market index refresh: success={success} fallback={fallback} unavailable={unavailable}".format(
            success=payload["success_count"],
            fallback=payload["fallback_count"],
            unavailable=payload["unavailable_count"],
        )
    )
    return 0 if payload["success_count"] or payload["fallback_count"] else 2


def _run_refresh_market_sector_history(args) -> int:
    if args.provider != "akshare":
        print(
            "refresh-market-sector-history requires --provider akshare; "
            "fixture data is not refreshed."
        )
        return 2
    try:
        symbols = _parse_market_sector_symbols(args.symbols)
        service = _build_cli_market_sector_service(args)
        payload = service.refresh_sector_histories(
            symbols,
            now=datetime.now(timezone.utc),
            as_of=_parse_refresh_as_of(args.as_of),
        )
    except ValueError as exc:
        print(str(exc))
        return 2
    except Exception as exc:
        print(f"Market sector history refresh failed: {exc}")
        return 2

    provider_config = load_provider_config(args.provider_config).akshare
    trace_path = write_provider_health_trace(
        as_of=str(payload["as_of"]),
        provider_health=tuple(getattr(service, "last_refresh_health", ())),
        output_dir=args.output_dir,
        filename_prefix="provider-sector-history",
        retention_days=provider_config.trace_retention_days,
        max_trace_files=provider_config.max_trace_files,
    )
    payload["provider_trace"] = str(trace_path.relative_to(args.output_dir))
    output_path = args.output_dir / "market" / "sector_history_refresh_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Provider trace: {trace_path}")
    print(f"Market sector history refresh report: {output_path}")
    print(
        "Market sector history refresh: success={success} fallback={fallback} unavailable={unavailable}".format(
            success=payload["success_count"],
            fallback=payload["fallback_count"],
            unavailable=payload["unavailable_count"],
        )
    )
    return 0 if payload["success_count"] or payload["fallback_count"] else 2


def _run_historical_backfill(args) -> int:
    try:
        nav_windows = parse_nav_windows(args.nav_windows)
        result = run_historical_backfill(
            provider=args.provider,
            start_date=args.start_date,
            end_date=args.end_date,
            output_dir=args.output_dir,
            funds_file=args.funds_file,
            cache_file=args.cache_file,
            themes_config=args.themes_config,
            top_n=args.top_n,
            min_theme_sample_size=args.min_theme_sample_size,
            nav_windows=nav_windows,
        )
    except ValueError as exc:
        print(str(exc))
        return 2
    print(f"Historical backfill report: {result.report_path}")
    print(f"Historical backfill summary: {result.summary_path}")
    print(f"Historical NAV summary: {result.nav_summary_path}")
    print(
        "Historical backfill: dates={dates} market_snapshots={snapshots} nav_summaries={nav}".format(
            dates=len(result.dates_processed),
            snapshots=result.market_snapshot_count,
            nav=result.nav_summary_count,
        )
    )
    if result.warnings:
        print("Historical backfill warnings: " + ", ".join(result.warnings))
    return 0 if result.status == "success" else 2


def _run_market_trend(args) -> int:
    report = build_market_trend_report(
        args.market_dir,
        days=args.days,
        min_snapshots=args.min_snapshots,
        top_n=args.top_n,
    )
    outputs = write_market_trend_outputs(report, args.output_dir)
    if args.json_output and args.json_output != outputs.report_path:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(outputs.report_path.read_text(encoding="utf-8"), encoding="utf-8")
    if args.summary_output and args.summary_output != outputs.summary_path:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(outputs.summary_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Market trend report: {outputs.report_path}")
    print(f"Market trend summary: {outputs.summary_path}")
    print(f"Market trend rankings: {outputs.rankings_path}")
    if outputs.run_report_path:
        print(f"Run bundle market trend report: {outputs.run_report_path}")
    if not report.enough_market_history:
        print("Market trend warning: insufficient market history; daily ops can continue.")
    return 0


def _run_portfolio_analysis(args) -> int:
    try:
        config = load_portfolio_config(args.portfolio_config)
    except Exception as exc:
        print(f"Failed to read portfolio config: {exc}")
        return 2
    report = build_portfolio_analysis_report(
        config,
        output_dir=args.output_dir,
        as_of=args.as_of or None,
    )
    json_path, markdown_path = write_portfolio_analysis_outputs(report, args.output_dir)
    print(f"Portfolio analysis report: {json_path}")
    print(f"Portfolio analysis summary: {markdown_path}")
    print(
        "Portfolio analysis: status={status} holdings={holdings} issues={issues}".format(
            status=report.get("status"),
            holdings=report.get("holding_count"),
            issues=report.get("observation_issue_count"),
        )
    )
    return 0


def _run_collect_news_evidence(args) -> int:
    try:
        payload = collect_news_evidence(
            source=args.source,
            fixtures_file=args.fixtures_file,
            output_dir=args.output_dir,
            as_of=args.as_of or None,
        )
    except Exception as exc:
        print(f"News evidence collection failed: {exc}")
        return 2
    report_path = args.output_dir / "news" / "news_evidence_report.json"
    summary_path = args.output_dir / "news" / "news_evidence_summary.md"
    run_path = args.output_dir / "runs" / str(payload.get("as_of")) / "news_evidence_report.json"
    print(f"News evidence report: {report_path}")
    print(f"News evidence summary: {summary_path}")
    if run_path.exists():
        print(f"Run bundle news evidence: {run_path}")
    print(
        "News evidence: evidence_count={count} low_confidence_count={low} duplicate_count={duplicates}".format(
            count=payload.get("evidence_count", 0),
            low=payload.get("low_confidence_count", 0),
            duplicates=payload.get("duplicate_count", 0),
        )
    )
    return 0


def _run_fund_detail(args) -> int:
    codes = []
    if getattr(args, "code", None):
        codes.append(args.code)
    if getattr(args, "codes", None):
        codes.extend(item.strip() for item in str(args.codes).split(",") if item.strip())
    codes = list(dict.fromkeys(normalize_fund_code(code) for code in codes if normalize_fund_code(code)))
    if not codes:
        print("fund-detail requires --code or --codes.")
        return 2
    details = build_fund_detail_views(
        codes=codes,
        output_dir=args.output_dir,
        watchlist_file=args.watchlist_file,
        portfolio_config=args.portfolio_config,
        cache_file=args.cache_file,
    )
    if len(details) == 1 and not getattr(args, "codes", None):
        json_path, md_path = write_single_fund_detail(
            details[0],
            args.output_dir,
            json_output=args.json_output,
            summary_output=args.summary_output,
        )
        print(f"Fund detail JSON: {json_path}")
        print(f"Fund detail summary: {md_path}")
        return 0
    json_path, md_path = write_watchlist_fund_details(
        details,
        args.output_dir,
        json_output=args.json_output,
        summary_output=args.summary_output,
    )
    print(f"Watchlist fund details JSON: {json_path}")
    print(f"Watchlist fund details summary: {md_path}")
    return 0


def _run_watchlist_detail(args) -> int:
    try:
        codes = list(load_watchlist_config(args.watchlist_file).codes)
    except Exception as exc:
        print(f"Failed to read watchlist: {exc}")
        return 2
    details = build_fund_detail_views(
        codes=codes,
        output_dir=args.output_dir,
        watchlist_file=args.watchlist_file,
        portfolio_config=args.portfolio_config,
        cache_file=args.cache_file,
    )
    json_path, md_path = write_watchlist_fund_details(
        details,
        args.output_dir,
        json_output=args.json_output,
        summary_output=args.summary_output,
    )
    print(f"Watchlist fund details JSON: {json_path}")
    print(f"Watchlist fund details summary: {md_path}")
    return 0


def _load_market_scan_funds(args, *, as_of: str) -> list[FundRecord]:
    if args.provider == "fixture":
        provider = FixtureProvider(args.funds_file)
        return provider.fetch_funds(as_of=as_of)
    cache = FundCache(args.cache_file)
    provider_config = load_provider_config(args.provider_config).akshare
    provider = AkshareProvider(
        cache=cache,
        allow_stale_cache=True,
        verbose=bool(getattr(args, "provider_verbose", False) or provider_config.verbose),
        timeout_seconds=provider_config.timeout_seconds,
        retry_count=provider_config.retry_count,
        retry_backoff_seconds=provider_config.retry_backoff_seconds,
    )
    try:
        funds = provider.fetch_funds(as_of=as_of)
    except ProviderUnavailable:
        funds = cache.load_funds(as_of=as_of, allow_stale=True) or cache.load_funds(allow_stale=True)
    if not funds:
        funds = cache.load_funds(as_of=as_of, allow_stale=True) or cache.load_funds(allow_stale=True)
    if not funds:
        raise ProviderUnavailable("provider returned no rows and cache is empty")
    return funds


def _run_daily_research(args) -> int:
    as_of = args.as_of or date.today().isoformat()
    started_at = _utc_now_iso()
    started_dt = datetime.now(timezone.utc)
    loop_config = load_research_loop_config(args.research_loop_config)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    experiment_config = load_experiment_scoring_config(args.experiment_config)
    run_dir = _resolve_research_run_dir(output_dir, as_of, loop_config.run_dir_pattern)
    steps = []

    def add_step(step_name, action, *, outputs=(), critical=False):
        result = execute_research_step(step_name, action, output_paths=tuple(outputs))
        steps.append(result)
        if result.status == "failed" and critical and not loop_config.continue_on_step_failure:
            raise RuntimeError(result.error_message or f"{step_name} failed")
        return result

    try:
        add_step(
            "daily",
            lambda: _run_report(args),
            outputs=(
                output_dir / "fund_agent_report.md",
                output_dir / "fund_agent_report.html",
                output_dir / "fund_agent_report.json",
                output_dir / "snapshots" / f"{as_of}.json",
                output_dir / "traces" / f"provider-{as_of}.json",
            ),
            critical=loop_config.fail_on_daily_error,
        )
        add_step(
            "validate_contract",
            lambda: _raise_if_contract_invalid(output_dir),
            critical=loop_config.fail_on_contract_error,
        )
        add_step(
            "generate_signal_candidates",
            lambda: generate_signal_candidates_file(
                output_dir / "fund_agent_report.json",
                output_dir / "signal_candidates.json",
            )
            and 0,
            outputs=(output_dir / "signal_candidates.json",),
            critical=loop_config.fail_on_experiment_error,
        )
        add_step(
            "experiment_scoring",
            lambda: run_experiment_scoring_file(
                report_path=output_dir / "fund_agent_report.json",
                signals_path=output_dir / "signal_candidates.json",
                config=experiment_config,
                output_path=output_dir / "experiment_scoring_report.json",
            )
            and 0,
            outputs=(output_dir / "experiment_scoring_report.json",),
            critical=loop_config.fail_on_experiment_error,
        )
        add_step(
            "explain_experiment_scoring",
            lambda: explain_experiment_scoring_file(
                output_dir / "experiment_scoring_report.json",
                output_dir / "experiment_scoring_explained.md",
            )
            and 0,
            outputs=(output_dir / "experiment_scoring_explained.md",),
            critical=loop_config.fail_on_experiment_error,
        )
        add_step(
            "compare_experiment_baseline",
            lambda: compare_experiment_baseline_file(
                report_path=output_dir / "fund_agent_report.json",
                experiment_path=output_dir / "experiment_scoring_report.json",
                output_path=output_dir / "experiment_baseline_comparison.json",
            )
            and 0,
            outputs=(output_dir / "experiment_baseline_comparison.json",),
            critical=loop_config.fail_on_experiment_error,
        )
        add_step(
            "experiment_config_sensitivity",
            lambda: run_experiment_config_sensitivity_file(
                report_path=output_dir / "fund_agent_report.json",
                signals_path=output_dir / "signal_candidates.json",
                config=experiment_config,
                output_path=output_dir / "experiment_config_sensitivity.json",
            )
            and 0,
            outputs=(output_dir / "experiment_config_sensitivity.json",),
            critical=loop_config.fail_on_experiment_error,
        )
        add_step(
            "review_signal_readiness",
            lambda: review_signal_readiness_file(
                signals_path=output_dir / "signal_candidates.json",
                stability_path=output_dir / "signal_stability_report.json",
                baseline_path=output_dir / "experiment_baseline_comparison.json",
                sensitivity_path=output_dir / "experiment_config_sensitivity.json",
                thresholds_path=args.thresholds,
                output_path=output_dir / "signal_readiness_review.json",
            )
            and 0,
            outputs=(output_dir / "signal_readiness_review.json", output_dir / "manual_review_queue.json"),
            critical=loop_config.fail_on_readiness_error,
        )
        add_step(
            "generate_signal_promotion_proposal",
            lambda: generate_signal_promotion_proposal_file(
                review_path=output_dir / "signal_readiness_review.json",
                output_path=output_dir / "signal_promotion_proposal.md",
            )
            and 0,
            outputs=(output_dir / "signal_promotion_proposal.md",),
            critical=loop_config.fail_on_readiness_error,
        )
    except RuntimeError as exc:
        print(f"Daily research stopped: {exc}")

    finished_at = _utc_now_iso()
    duration_ms = int((datetime.now(timezone.utc) - started_dt).total_seconds() * 1000)
    status = _daily_research_status(steps, loop_config)
    write_daily_research_summary(
        output_dir=output_dir,
        as_of=as_of,
        steps=tuple(steps),
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        status=status,
        missing_artifacts=[],
    )
    bundle = None
    missing_artifacts = []
    if loop_config.copy_artifacts:
        bundle = write_run_bundle(
            output_dir=output_dir,
            as_of=as_of,
            run_dir=run_dir,
            include_markdown_reports=loop_config.include_markdown_reports,
            include_json_reports=loop_config.include_json_reports,
        )
        missing_artifacts = list(bundle.missing_artifacts)
    write_daily_research_summary(
        output_dir=output_dir,
        as_of=as_of,
        steps=tuple(steps),
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        status=status,
        missing_artifacts=missing_artifacts,
    )
    if loop_config.copy_artifacts:
        bundle = write_run_bundle(
            output_dir=output_dir,
            as_of=as_of,
            run_dir=run_dir,
            include_markdown_reports=loop_config.include_markdown_reports,
            include_json_reports=loop_config.include_json_reports,
        )
    else:
        run_dir.mkdir(parents=True, exist_ok=True)
    _write_run_metadata(
        run_dir,
        as_of=as_of,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        steps=steps,
        status=status,
    )
    print(f"Daily research summary: {output_dir / 'daily_research_summary.md'}")
    print(f"Daily research JSON: {output_dir / 'daily_research_summary.json'}")
    print(f"Run bundle: {run_dir}")
    return 0 if status == "success" else 1


def _run_weekly_research(args) -> int:
    markdown_path, json_path, _payload = run_weekly_research(
        runs_dir=args.runs_dir,
        output_path=args.output,
        json_output_path=args.json_output,
        days=args.days,
        review_state_path=args.review_state,
    )
    print(f"Weekly research summary: {markdown_path}")
    print(f"Weekly research JSON: {json_path}")
    return 0


def _run_update_review_state(args) -> int:
    try:
        item = update_review_state(
            state_path=args.state,
            review_id=args.review_id,
            signal_id=args.signal_id,
            status=args.status,
            reviewer=args.reviewer,
            note=args.note,
            evidence_refs=args.evidence_ref or None,
        )
    except ValueError as exc:
        print(str(exc))
        return 2
    print(f"Review state updated: {item['review_id']} status={item['status']}")
    return 0


def _run_list_review_state(args) -> int:
    items = list_review_state(args.state)
    summary = summarize_review_state(items)
    if args.summary_output:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(
        "Review state: total={total} approved_count={approved} rejected_count={rejected} needs_more_data_count={needs} unresolved_count={unresolved}".format(
            total=summary["total_review_items"],
            approved=summary["approved_count"],
            rejected=summary["rejected_count"],
            needs=summary["needs_more_data_count"],
            unresolved=summary["unresolved_count"],
        )
    )
    for item in items:
        print(f"- {item.get('review_id')}: {item.get('signal_id')} status={item.get('status')} note={item.get('note', '')}")
    return 0


def _run_generate_evidence_dashboard(args) -> int:
    path = generate_evidence_dashboard(
        runs_dir=args.runs_dir,
        review_state_path=args.review_state,
        output_dir=args.output_dir,
        days=args.days,
    )
    print(f"Evidence dashboard manifest: {path}")
    return 0


def _run_evaluate_long_horizon_stability(args) -> int:
    result = evaluate_long_horizon_stability(runs_dir=args.runs_dir, days=args.days)
    path = write_long_horizon_stability(result, args.output)
    print(f"Long-horizon stability: {path}")
    print(
        "runs_processed={runs} enough_history={enough} blockers={blockers}".format(
            runs=result["runs_processed"],
            enough=result["enough_history"],
            blockers=",".join(result["blockers"]) or "none",
        )
    )
    return 0


def _run_ops_status(args) -> int:
    if args.write_latest_summary:
        latest = write_latest_summary(args.output_dir)
        print(f"Latest summary: {latest}")
    status = build_ops_status(args.output_dir)
    if args.json_output:
        path = write_ops_status(status, args.json_output)
        print(f"Ops status JSON: {path}")
    print(
        "Ops status: {status} latest_run={run} dashboard={dashboard}".format(
            status=status["overall_status"],
            run=(status.get("latest_run") or {}).get("as_of") or "--",
            dashboard=status["artifacts"]["dashboard_index"]["exists"],
        )
    )
    return 0 if status["overall_status"] in {"ok", "warning"} else 1


def _run_web_console(args) -> int:
    if args.dry_run:
        state = build_web_console_state(output_dir=args.output_dir, review_state_path=args.review_state)
        print(
            "Web console ready: output_dir={output_dir} ops_ready={ops_ready} dashboard_ready={dashboard_ready}".format(
                output_dir=state["output_dir"],
                ops_ready=state["ops_status"].get("ops_ready"),
                dashboard_ready=state["ops_status"].get("dashboard_ready"),
            )
        )
        print("not_production_model=true")
        print("main_score_changed=false")
        print("main_risk_changed=false")
        return 0
    if not _streamlit_available():
        print("Streamlit is not installed; install streamlit or run web-console --dry-run to validate local outputs.")
        return 2
    script = Path(__file__).with_name("web_console.py")
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(script),
        "--server.address",
        args.host,
        "--server.port",
        str(args.port),
        "--",
        "--output-dir",
        str(args.output_dir),
        "--daily-provider",
        args.provider,
    ]
    if args.review_state is not None:
        command.extend(["--review-state", str(args.review_state)])
    result = subprocess.run(command, check=False)
    return int(getattr(result, "returncode", result if isinstance(result, int) else 0))


def _streamlit_available() -> bool:
    return importlib.util.find_spec("streamlit") is not None


def _default_product_web_static_dir() -> Path:
    return Path(__file__).resolve().parent / "web_static"


def _product_web_dependencies_available() -> bool:
    return importlib.util.find_spec("fastapi") is not None and importlib.util.find_spec("uvicorn") is not None


def _run_product_web(args) -> int:
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        print("Product web only supports a loopback host by default; use 127.0.0.1, localhost, or ::1.")
        return 2
    api_ready = _product_web_dependencies_available()
    static_ready = (args.static_dir / "index.html").is_file()
    if args.dry_run:
        print(
            "Product web ready: output_dir={output_dir} static_dir={static_dir} api_ready={api_ready} static_ready={static_ready}".format(
                output_dir=args.output_dir,
                static_dir=args.static_dir,
                api_ready=str(api_ready).lower(),
                static_ready=str(static_ready).lower(),
            )
        )
        print("not_production_model=true")
        print("main_score_changed=false")
        print("main_risk_changed=false")
        return 0 if api_ready and static_ready else 2
    if not api_ready:
        print('FastAPI/Uvicorn are not installed; install the "webapp" optional dependencies.')
        return 2
    if not static_ready:
        print(f"Product web build is missing: {args.static_dir / 'index.html'}; run npm run build in web/.")
        return 2
    return _run_product_web_server(
        output_dir=args.output_dir,
        review_state_path=args.review_state,
        static_dir=args.static_dir,
        host=args.host,
        port=args.port,
    )


def _run_product_web_server(
    *,
    output_dir: Path,
    review_state_path: Path | None,
    static_dir: Path,
    host: str,
    port: int,
) -> int:
    import uvicorn

    from .web_api import create_web_app

    app = create_web_app(
        output_dir=output_dir,
        review_state_path=review_state_path,
        static_dir=static_dir,
    )
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


def _raise_if_contract_invalid(output_dir: Path) -> int:
    summary = validate_output_dir(output_dir)
    if not summary.results:
        raise RuntimeError("no contract files found")
    if not summary.ok:
        errors = [
            f"{result.contract_type}:{'; '.join(result.errors)}"
            for result in summary.results
            if not result.ok
        ]
        raise RuntimeError("contract validation failed: " + " | ".join(errors))
    return 0


def _daily_research_status(steps, loop_config) -> str:
    critical = set()
    if loop_config.fail_on_daily_error:
        critical.add("daily")
    if loop_config.fail_on_contract_error:
        critical.add("validate_contract")
    if loop_config.fail_on_experiment_error:
        critical.update(
            {
                "generate_signal_candidates",
                "experiment_scoring",
                "explain_experiment_scoring",
                "compare_experiment_baseline",
                "experiment_config_sensitivity",
            }
        )
    if loop_config.fail_on_readiness_error:
        critical.update({"review_signal_readiness", "generate_signal_promotion_proposal"})
    return "failed" if any(step.step_name in critical and step.status == "failed" for step in steps) else "success"


def _write_run_metadata(
    run_dir: Path,
    *,
    as_of: str,
    started_at: str,
    finished_at: str,
    duration_ms: int,
    steps,
    status: str,
) -> None:
    payload = {
        "schema_version": "1.0",
        "generated_at": finished_at,
        "generator": "fund_agent",
        "as_of": as_of,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": duration_ms,
        "steps": [asdict(step) for step in steps],
        "status": status,
        "provenance": collect_runtime_provenance(),
    }
    (run_dir / "run_metadata.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _resolve_research_run_dir(output_dir: Path, as_of: str, pattern: str) -> Path:
    default_pattern = "outputs/runs/{as_of}"
    if pattern == default_pattern:
        return output_dir / "runs" / as_of
    return Path(pattern.format(as_of=as_of, output_dir=str(output_dir)))


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

    daily_research = subparsers.add_parser("daily-research", help="串联每日研究证据闭环，不修改主评分/风险")
    add_report_args(
        daily_research,
        include_portfolio=True,
        default_watchlist=DEFAULT_WATCHLIST_FILE,
        default_portfolio_config=DEFAULT_PORTFOLIO_CONFIG,
        default_provider="fixture",
    )
    daily_research.add_argument("--experiment-config", type=Path, default=DEFAULT_EXPERIMENT_SCORING_CONFIG)
    daily_research.add_argument("--thresholds", type=Path, default=DEFAULT_SIGNAL_THRESHOLD_CONFIG)
    daily_research.add_argument("--research-loop-config", type=Path, default=DEFAULT_RESEARCH_LOOP_CONFIG)
    daily_research.set_defaults(func=_run_daily_research)

    market_scan = subparsers.add_parser("market-scan", help="生成全市场基金/ETF 观察层，不修改主评分/风险")
    market_scan.add_argument("--provider", choices=["fixture", "akshare"], default="fixture")
    market_scan.add_argument("--funds-file", type=Path, default=DEFAULT_FUNDS_FILE)
    market_scan.add_argument("--cache-file", type=Path, default=DEFAULT_CACHE_FILE)
    market_scan.add_argument("--provider-config", type=Path, default=DEFAULT_PROVIDER_CONFIG)
    market_scan.add_argument("--themes-config", type=Path, default=DEFAULT_MARKET_THEMES_CONFIG)
    market_scan.add_argument("--output-dir", type=Path, default=Path("outputs"))
    market_scan.add_argument("--as-of", default="")
    market_scan.add_argument("--top-n", type=int, default=20)
    market_scan.add_argument("--min-theme-sample-size", type=int, default=5)
    market_scan.add_argument("--provider-verbose", action="store_true")
    market_scan.set_defaults(func=_run_market_scan)

    refresh_market_history = subparsers.add_parser(
        "refresh-market-history",
        help="刷新允许的主要指数历史缓存；仅支持 akshare，不修改主评分/风险",
    )
    refresh_market_history.add_argument("--provider", choices=["fixture", "akshare"], default="akshare")
    refresh_market_history.add_argument("--cache-file", type=Path, default=DEFAULT_CACHE_FILE)
    refresh_market_history.add_argument("--provider-config", type=Path, default=DEFAULT_PROVIDER_CONFIG)
    refresh_market_history.add_argument("--output-dir", type=Path, default=Path("outputs"))
    refresh_market_history.add_argument("--as-of", default="")
    refresh_market_history.add_argument("--provider-verbose", action="store_true")
    refresh_market_history.set_defaults(func=_run_refresh_market_history)

    refresh_market_sector_history = subparsers.add_parser(
        "refresh-market-sector-history",
        help="刷新明确行业板块的历史缓存；仅支持 akshare，不修改主评分/风险",
    )
    refresh_market_sector_history.add_argument(
        "--provider",
        choices=["fixture", "akshare"],
        default="akshare",
    )
    refresh_market_sector_history.add_argument(
        "--symbols",
        required=True,
        help="逗号分隔的行业 BK 代码，例如 BK1042,BK1036",
    )
    refresh_market_sector_history.add_argument(
        "--cache-file",
        type=Path,
        default=DEFAULT_CACHE_FILE,
    )
    refresh_market_sector_history.add_argument(
        "--provider-config",
        type=Path,
        default=DEFAULT_PROVIDER_CONFIG,
    )
    refresh_market_sector_history.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
    )
    refresh_market_sector_history.add_argument("--as-of", default="")
    refresh_market_sector_history.add_argument(
        "--provider-verbose",
        action="store_true",
    )
    refresh_market_sector_history.set_defaults(
        func=_run_refresh_market_sector_history
    )

    refresh_fund_profile_reference = subparsers.add_parser(
        "refresh-fund-profile-reference",
        help="显式刷新基金目录和全量申购状态快照；不进入 daily 或详情请求",
    )
    refresh_fund_profile_reference.add_argument(
        "--provider",
        choices=["akshare"],
        default="akshare",
    )
    refresh_fund_profile_reference.add_argument(
        "--cache-file",
        type=Path,
        default=DEFAULT_CACHE_FILE,
    )
    refresh_fund_profile_reference.add_argument(
        "--provider-config",
        type=Path,
        default=DEFAULT_PROVIDER_CONFIG,
    )
    refresh_fund_profile_reference.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
    )
    refresh_fund_profile_reference.add_argument("--as-of", default="")
    refresh_fund_profile_reference.add_argument("--reference-ttl-days", type=int, default=1)
    refresh_fund_profile_reference.add_argument("--minimum-entry-count", type=int, default=100)
    refresh_fund_profile_reference.add_argument(
        "--catalog-minimum-mapped-ratio",
        type=float,
        default=0.35,
    )
    refresh_fund_profile_reference.add_argument(
        "--purchase-minimum-mapped-ratio",
        type=float,
        default=0.8,
    )
    refresh_fund_profile_reference.add_argument("--provider-verbose", action="store_true")
    refresh_fund_profile_reference.set_defaults(
        func=_run_refresh_fund_profile_reference,
        profile_cache_ttl_days=7,
    )

    fetch_fund_profile = subparsers.add_parser(
        "fetch-fund-profile",
        help="按代码读取或补全基金概况、交易规则与费率；不调用全量目录/申购接口",
    )
    fetch_fund_profile.add_argument("--code", required=True)
    fetch_fund_profile.add_argument("--cache-file", type=Path, default=DEFAULT_CACHE_FILE)
    fetch_fund_profile.add_argument(
        "--provider-config",
        type=Path,
        default=DEFAULT_PROVIDER_CONFIG,
    )
    fetch_fund_profile.add_argument("--output-dir", type=Path, default=Path("outputs"))
    fetch_fund_profile.add_argument("--as-of", default="")
    fetch_fund_profile.add_argument("--profile-cache-ttl-days", type=int, default=7)
    fetch_fund_profile.add_argument("--provider-verbose", action="store_true")
    fetch_fund_profile.set_defaults(func=_run_fetch_fund_profile)

    historical = subparsers.add_parser("historical-backfill", help="生成历史回填观察数据，不修改主评分/风险")
    historical.add_argument("--provider", choices=["fixture", "cache"], default="fixture")
    historical.add_argument("--start-date", required=True)
    historical.add_argument("--end-date", required=True)
    historical.add_argument("--output-dir", type=Path, default=Path("outputs"))
    historical.add_argument("--funds-file", type=Path, default=DEFAULT_FUNDS_FILE)
    historical.add_argument("--cache-file", type=Path, default=DEFAULT_CACHE_FILE)
    historical.add_argument("--themes-config", type=Path, default=DEFAULT_MARKET_THEMES_CONFIG)
    historical.add_argument("--top-n", type=int, default=20)
    historical.add_argument("--min-theme-sample-size", type=int, default=5)
    historical.add_argument("--nav-windows", default="1m,3m,6m")
    historical.set_defaults(func=_run_historical_backfill)

    market_trend = subparsers.add_parser("market-trend", help="基于 market snapshots 生成板块趋势观察，不修改主评分/风险")
    market_trend.add_argument("--market-dir", type=Path, default=Path("outputs/market"))
    market_trend.add_argument("--output-dir", type=Path, default=Path("outputs"))
    market_trend.add_argument("--days", type=int, default=30, choices=[7, 30, 60])
    market_trend.add_argument("--min-snapshots", type=int, default=3)
    market_trend.add_argument("--top-n", type=int, default=20)
    market_trend.add_argument("--json-output", type=Path)
    market_trend.add_argument("--summary-output", type=Path)
    market_trend.set_defaults(func=_run_market_trend)

    portfolio_analysis = subparsers.add_parser("portfolio-analysis", help="生成独立组合观察报告，不修改主评分/风险")
    portfolio_analysis.add_argument("--portfolio-config", type=Path, default=DEFAULT_PORTFOLIO_CONFIG)
    portfolio_analysis.add_argument("--output-dir", type=Path, default=Path("outputs"))
    portfolio_analysis.add_argument("--as-of", default="")
    portfolio_analysis.set_defaults(func=_run_portfolio_analysis)

    news_evidence = subparsers.add_parser("collect-news-evidence", help="收集新闻/公告证据候选，不修改主评分/风险")
    news_evidence.add_argument("--source", choices=["fixture"], default="fixture")
    news_evidence.add_argument("--fixtures-file", type=Path, default=DEFAULT_NEWS_EVIDENCE_FILE)
    news_evidence.add_argument("--output-dir", type=Path, default=Path("outputs"))
    news_evidence.add_argument("--as-of", default="")
    news_evidence.set_defaults(func=_run_collect_news_evidence)

    fund_detail = subparsers.add_parser("fund-detail", help="生成单只或多只基金详情观察层，不修改主评分/风险")
    fund_detail.add_argument("--code")
    fund_detail.add_argument("--codes")
    fund_detail.add_argument("--watchlist-file", type=Path, default=DEFAULT_WATCHLIST_FILE)
    fund_detail.add_argument("--portfolio-config", type=Path, default=DEFAULT_PORTFOLIO_CONFIG)
    fund_detail.add_argument("--cache-file", type=Path, default=DEFAULT_CACHE_FILE)
    fund_detail.add_argument("--output-dir", type=Path, default=Path("outputs"))
    fund_detail.add_argument("--json-output", type=Path)
    fund_detail.add_argument("--summary-output", type=Path)
    fund_detail.set_defaults(func=_run_fund_detail)

    watchlist_detail = subparsers.add_parser("watchlist-detail", help="生成自选池基金详情观察层，不修改主评分/风险")
    watchlist_detail.add_argument("--watchlist-file", type=Path, default=DEFAULT_WATCHLIST_FILE)
    watchlist_detail.add_argument("--portfolio-config", type=Path, default=DEFAULT_PORTFOLIO_CONFIG)
    watchlist_detail.add_argument("--cache-file", type=Path, default=DEFAULT_CACHE_FILE)
    watchlist_detail.add_argument("--output-dir", type=Path, default=Path("outputs"))
    watchlist_detail.add_argument("--json-output", type=Path)
    watchlist_detail.add_argument("--summary-output", type=Path)
    watchlist_detail.set_defaults(func=_run_watchlist_detail)

    weekly_research = subparsers.add_parser("weekly-research", help="聚合 daily-research run bundle，生成每周证据摘要")
    weekly_research.add_argument("--runs-dir", type=Path, default=Path("outputs/runs"))
    weekly_research.add_argument("--output", type=Path, default=Path("outputs/weekly_research_summary.md"))
    weekly_research.add_argument("--json-output", type=Path, default=Path("outputs/weekly_research_summary.json"))
    weekly_research.add_argument("--days", type=int, default=7)
    weekly_research.add_argument("--review-state", type=Path, default=DEFAULT_REVIEW_STATE_FILE)
    weekly_research.set_defaults(func=_run_weekly_research)

    update_review = subparsers.add_parser("update-review-state", help="新增或更新人工审核状态，不修改阈值配置或主模型")
    update_review.add_argument("--review-id", required=True)
    update_review.add_argument(
        "--status",
        required=True,
        choices=[
            "open",
            "approved_for_more_experiment",
            "rejected",
            "needs_more_data",
            "approved_for_main_candidate",
        ],
    )
    update_review.add_argument("--note", default="")
    update_review.add_argument("--reviewer", default="")
    update_review.add_argument("--signal-id")
    update_review.add_argument("--evidence-ref", action="append")
    update_review.add_argument("--state", type=Path, default=DEFAULT_REVIEW_STATE_FILE)
    update_review.set_defaults(func=_run_update_review_state)

    list_review = subparsers.add_parser("list-review-state", help="查看人工审核状态摘要")
    list_review.add_argument("--state", type=Path, default=DEFAULT_REVIEW_STATE_FILE)
    list_review.add_argument("--summary-output", type=Path)
    list_review.set_defaults(func=_run_list_review_state)

    dashboard = subparsers.add_parser("generate-evidence-dashboard", help="从 JSON 证据包生成静态 dashboard")
    dashboard.add_argument("--runs-dir", type=Path, default=Path("outputs/runs"))
    dashboard.add_argument("--review-state", type=Path, default=DEFAULT_REVIEW_STATE_FILE)
    dashboard.add_argument("--output-dir", type=Path, default=Path("outputs/dashboard"))
    dashboard.add_argument("--days", type=int, default=30)
    dashboard.set_defaults(func=_run_generate_evidence_dashboard)

    long_horizon = subparsers.add_parser("evaluate-long-horizon-stability", help="评估长周期信号稳定性门槛，不修改主模型")
    long_horizon.add_argument("--runs-dir", type=Path, default=Path("outputs/runs"))
    long_horizon.add_argument("--days", type=int, default=30)
    long_horizon.add_argument("--output", type=Path, default=Path("outputs/long_horizon_stability.json"))
    long_horizon.set_defaults(func=_run_evaluate_long_horizon_stability)

    ops_status = subparsers.add_parser("ops-status", help="查看本地 daily ops 运行状态，并可写 latest_summary.md")
    ops_status.add_argument("--output-dir", type=Path, default=Path("outputs"))
    ops_status.add_argument("--json-output", type=Path)
    ops_status.add_argument("--write-latest-summary", action="store_true")
    ops_status.set_defaults(func=_run_ops_status)

    web_console = subparsers.add_parser("web-console", help="启动本地 Web Console v1，不修改主评分/风险")
    web_console.add_argument("--output-dir", type=Path, default=Path("outputs"))
    web_console.add_argument("--review-state", type=Path)
    web_console.add_argument("--provider", choices=["fixture", "akshare"], default="fixture")
    web_console.add_argument("--host", default="127.0.0.1")
    web_console.add_argument("--port", type=int, default=8501)
    web_console.add_argument("--dry-run", action="store_true")
    web_console.set_defaults(func=_run_web_console)

    product_web = subparsers.add_parser("product-web", help="启动本地产品化 Web Console，保留研究只读边界")
    product_web.add_argument("--output-dir", type=Path, default=Path("outputs"))
    product_web.add_argument("--review-state", type=Path)
    product_web.add_argument("--static-dir", type=Path, default=_default_product_web_static_dir())
    product_web.add_argument("--host", default="127.0.0.1")
    product_web.add_argument("--port", type=int, default=8768)
    product_web.add_argument("--dry-run", action="store_true")
    product_web.set_defaults(func=_run_product_web)

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
    validate.add_argument("--research-context", type=Path)
    validate.add_argument("--evidence-bundle", type=Path)
    validate.add_argument("--research-answer", type=Path)
    validate.add_argument("--mcp-result", type=Path)
    validate.add_argument("--release-readiness", type=Path)
    validate.add_argument("--fund-profile", type=Path)
    validate.set_defaults(func=_run_validate_contract)

    release_readiness = subparsers.add_parser(
        "release-readiness",
        help="只读检查 V2 contract、性能和真实 daily run 发布门禁",
    )
    release_readiness.add_argument("--output-dir", type=Path, default=Path("outputs"))
    release_readiness.add_argument("--minimum-valid-runs", type=int, default=3)
    release_readiness.add_argument("--release-target", default="v2.0.0-rc.1")
    release_readiness.add_argument(
        "--observation-mode",
        choices=["historical_compat", "post_rc"],
        default="historical_compat",
    )
    release_readiness.add_argument("--required-app-version")
    release_readiness.add_argument("--required-git-commit")
    release_readiness.add_argument("--json-output", type=Path)
    release_readiness.set_defaults(func=_run_release_readiness)

    research_query = subparsers.add_parser(
        "research-query",
        help="从 V1 JSON artifact 生成紧凑只读研究上下文，不解析 Markdown",
    )
    research_query.add_argument("--output-dir", type=Path, default=Path("outputs"))
    research_query.add_argument("--topic", choices=SUPPORTED_RESEARCH_TOPICS, required=True)
    research_query.add_argument("--code")
    research_query.add_argument("--output", type=Path)
    research_query.set_defaults(func=_run_research_query)

    research_evidence = subparsers.add_parser(
        "build-research-evidence",
        help="从 Research Context 生成带 JSON Pointer 引用的 Evidence Bundle",
    )
    research_evidence.add_argument("--context", type=Path)
    research_evidence.add_argument("--output-dir", type=Path, default=Path("outputs"))
    research_evidence.add_argument("--output", type=Path)
    research_evidence.set_defaults(func=_run_build_research_evidence)

    research_ask = subparsers.add_parser(
        "research-ask",
        help="基于本地 JSON 证据回答受约束的只读研究问题",
    )
    research_ask.add_argument("--question", required=True)
    research_ask.add_argument("--output-dir", type=Path, default=Path("outputs"))
    research_ask.add_argument("--output", type=Path)
    research_ask.add_argument("--markdown-output", type=Path)
    research_ask.add_argument("--audit-output", type=Path)
    research_ask.set_defaults(func=_run_research_ask)

    mcp_server = subparsers.add_parser(
        "mcp-server",
        help="启动 optional 的本地只读 Research MCP server",
    )
    mcp_server.add_argument("--output-dir", type=Path, default=Path("outputs"))
    mcp_server.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
    )
    mcp_server.add_argument("--timeout-seconds", type=float, default=10.0)
    mcp_server.add_argument("--audit-output", type=Path)
    mcp_server.add_argument("--dry-run", action="store_true")
    mcp_server.set_defaults(func=_run_mcp_server)

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

    readiness = subparsers.add_parser("review-signal-readiness", help="生成信号阈值候选和人工审批闸门输出")
    readiness.add_argument("--signals", type=Path, required=True)
    readiness.add_argument("--stability", type=Path, required=True)
    readiness.add_argument("--baseline", type=Path, required=True)
    readiness.add_argument("--sensitivity", type=Path, required=True)
    readiness.add_argument("--thresholds", type=Path, default=DEFAULT_SIGNAL_THRESHOLD_CONFIG)
    readiness.add_argument("--output", type=Path, default=Path("outputs/signal_readiness_review.json"))
    readiness.set_defaults(func=_run_review_signal_readiness)

    proposal = subparsers.add_parser("generate-signal-promotion-proposal", help="生成信号 promotion proposal Markdown")
    proposal.add_argument("--review", type=Path, required=True)
    proposal.add_argument("--output", type=Path, default=Path("docs/reviews/signal_promotion_proposal.md"))
    proposal.set_defaults(func=_run_generate_signal_promotion_proposal)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
