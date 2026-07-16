export type Availability = "available" | "missing";

export type ApiResource<T> = {
  availability: Availability;
  generated_at: string | null;
  data: T;
};

export type DailyStatus = {
  as_of?: string | null;
  status?: string | null;
  data_quality_grade?: string | null;
};

export type OverviewData = {
  ops_status?: {
    ops_ready?: boolean;
    dashboard_ready?: boolean;
    latest_run?: { as_of?: string; status?: string };
    daily?: DailyStatus;
    latest_market_theme_count?: number;
    watchlist_detail_count?: number;
    latest_portfolio_holding_count?: number;
    main_model_ready?: boolean;
    main_model_blockers?: string[];
  };
  latest_summary_data?: Record<string, unknown>;
  review_queue_count?: number;
  review_state_summary?: { unresolved_count?: number };
  not_production_model?: boolean;
  main_score_changed?: boolean;
  main_risk_changed?: boolean;
};

export type ThemeSummary = {
  theme?: string;
  avg_return_1w?: number | null;
  avg_return_1m?: number | null;
  avg_return_3m?: number | null;
  avg_return_6m?: number | null;
  avg_return_1y?: number | null;
  positive_ratio_1m?: number | null;
  sample_size?: number | null;
  fund_count?: number | null;
  etf_count?: number | null;
  data_quality_grade?: string | null;
  warnings?: string[];
};

export type ThemeTrend = {
  theme?: string;
  hot_ratio?: number | null;
  latest_rank?: number | null;
  previous_rank?: number | null;
  rank_change?: number | null;
  latest_sample_size?: number | null;
  latest_data_quality_grade?: string | null;
  warnings?: string[];
};

export type MarketData = {
  intelligence?: {
    as_of?: string | null;
    total_funds?: number;
    total_etfs?: number;
    source?: string | null;
    data_quality_summary?: {
      grade?: string | null;
      stale_record_count?: number;
      warnings?: string[];
    };
    top_themes?: ThemeSummary[];
    hot_theme_candidates?: ThemeSummary[];
    themes?: ThemeSummary[];
    warnings?: string[];
  };
  trend?: {
    latest_as_of?: string | null;
    snapshots_processed?: number;
    minimum_required_snapshots?: number;
    enough_market_history?: boolean;
    persistent_hot_themes?: ThemeTrend[];
    new_hot_themes?: ThemeTrend[];
    rising_themes?: ThemeTrend[];
    falling_themes?: ThemeTrend[];
    data_quality_trend?: Array<{
      as_of?: string;
      warning_count?: number;
      insufficient_sample_theme_count?: number;
    }>;
    warnings?: string[];
  };
};

export type FundDetailItem = {
  code?: string;
  name?: string;
  fund_type?: string;
  primary_theme?: string;
  themes?: string[];
  nav?: number | null;
  scale?: number | null;
  rating?: string | number | null;
  fund_company?: string | null;
  fund_manager?: string | null;
  inception_date?: string | null;
  source?: string | null;
  as_of?: string | null;
  data_quality_grade?: string | null;
  data_quality_warnings?: string[];
  missing_fields?: string[];
  return_windows?: Record<string, { total_return?: number | null; max_drawdown?: number | null; volatility?: number | null }>;
  data_coverage?: { coverage_ratio?: number | null; status?: string | null };
  signal_context?: { signal_status?: string; signal_reasons?: string[] };
};

export type FundsData = {
  details?: {
    as_of?: string | null;
    detail_count?: number;
    missing_count?: number;
    warning_count?: number;
    coverage_summary?: { average_coverage_ratio?: number | null };
    fund_details?: FundDetailItem[];
    funds?: FundDetailItem[];
  };
  signal_candidates?: {
    summary?: { eligible_count?: number; excluded_count?: number; display_only_count?: number };
  };
};

export type PortfolioPosition = {
  code?: string;
  name?: string;
  shares?: number | null;
  cost_value?: number | null;
  current_value?: number | null;
  weight?: number | null;
  source?: string | null;
  primary_theme?: string | null;
  unrealized_return_pct?: number | null;
  valuation_confidence?: string | null;
};

export type PortfolioData = {
  as_of?: string | null;
  status?: string | null;
  portfolio_name?: string | null;
  holding_count?: number;
  total_value?: number | null;
  cash_available?: number | null;
  total_unrealized_return_pct?: number | null;
  positions?: PortfolioPosition[];
  theme_exposure?: Record<string, { holding_count?: number; current_value?: number; weight?: number }>;
  fund_type_exposure?: Record<string, { holding_count?: number; current_value?: number; weight?: number }>;
  observation_issues?: Array<{ issue_type?: string; severity?: string; message?: string; metadata?: Record<string, unknown> }>;
  warnings?: string[];
};

export type NewsEvidenceItem = {
  evidence_id?: string;
  title?: string;
  published_at?: string | null;
  source?: string | null;
  source_quality?: string | null;
  evidence_strength?: string | null;
  low_confidence?: boolean;
  related_themes?: string[];
  related_funds?: string[];
  url?: string | null;
  warnings?: string[];
};

export type NewsData = {
  as_of?: string | null;
  evidence_count?: number;
  low_confidence_count?: number;
  duplicate_count?: number;
  source?: string | null;
  items?: NewsEvidenceItem[];
  warnings?: string[];
};

export type CopilotCitation = {
  evidence_id?: string;
  source?: string;
  as_of?: string | null;
  quality_grade?: string | null;
  stale?: boolean;
  excerpt?: unknown;
};

export type CopilotFinding = {
  finding_id?: string;
  label?: string;
  value?: unknown;
  quality_grade?: string | null;
  warnings?: string[];
  citations?: CopilotCitation[];
};

export type CopilotResponseData = {
  answer?: Record<string, unknown>;
  view_model?: {
    status?: string;
    tone?: string;
    summary?: string;
    as_of?: string | null;
    intent?: string;
    confidence?: string;
    review_required?: boolean;
    finding_count?: number;
    evidence_count?: number;
    findings?: CopilotFinding[];
    data_gaps?: string[];
    warnings?: string[];
  };
};

export type ReviewItem = {
  review_id?: string;
  signal_id?: string;
  status?: string;
  reason?: string;
  excluded_reason?: string;
  note?: string;
  reviewer?: string;
};

export type ReviewsData = {
  queue?: ReviewItem[];
  state?: ReviewItem[];
  summary?: {
    total_review_items?: number;
    unresolved_count?: number;
    needs_more_data_count?: number;
    approved_count?: number;
  };
};

export type ReportItem = {
  report_id: string;
  label: string;
  relative_path: string;
  kind: string;
  exists: boolean;
  updated_at: string | null;
};

export type ReportsData = { reports?: ReportItem[] };
