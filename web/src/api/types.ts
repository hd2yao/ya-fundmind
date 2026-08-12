export type Availability = "available" | "missing";

export type ApiResource<T> = {
  availability: Availability;
  generated_at: string | null;
  data: T;
};

export type ProductDataStatus = {
  state: "updated" | "attention" | "limited" | "unavailable" | string;
  label: string;
  description: string;
  as_of: string | null;
};

export type ProductThemeSummary = {
  name: string | null;
  returns: Partial<Record<"1w" | "1m" | "3m" | "6m" | "1y", number | null>>;
  positive_ratio_1m: number | null;
  sample_size: number | null;
  fund_count: number | null;
  etf_count: number | null;
  data_status: ProductDataStatus;
};

export type ProductThemeChange = {
  name: string | null;
  rank: number | null;
  rank_change: number | null;
};

export type ProductMarketData = {
  as_of: string | null;
  coverage: { fund_count: number | null; etf_count: number | null };
  data_status: ProductDataStatus;
  themes: ProductThemeSummary[];
  trend: {
    persistent: ProductThemeChange[];
    new: ProductThemeChange[];
    rising: ProductThemeChange[];
    falling: ProductThemeChange[];
  };
};

export type ProductMarketHistoryPoint = {
  date: string | null;
  open: number | null;
  close: number | null;
  high: number | null;
  low: number | null;
  volume: number | null;
  turnover: number | null;
  change_pct: number | null;
};

export type ProductMarketHistoryResponse = {
  availability: Availability;
  symbol: string | null;
  name: string;
  range: MarketIndexWindow;
  point_count: number;
  required_points: number | null;
  points: ProductMarketHistoryPoint[];
  data_date: string | null;
  data_status: ProductDataStatus;
};

export type ProductMarketSectorItem = {
  symbol: string;
  name: string;
  latest: number | null;
  change_pct: number | null;
  rise_count: number | null;
  fall_count: number | null;
  leader_name: string | null;
  leader_change_pct: number | null;
};

export type ProductMarketSectorSearchResponse = {
  availability: Availability;
  items: ProductMarketSectorItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  query: string;
  data_date: string | null;
  data_status: ProductDataStatus;
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

export type MarketIndexWindow = "1m" | "3m" | "6m" | "1y" | "all";

export type MarketIndexHistoryPoint = {
  date: string;
  open: number | null;
  close: number | null;
  high: number | null;
  low: number | null;
  volume: number | null;
  turnover: number | null;
  turnover_rate?: number | null;
  change_pct: number | null;
  source: string;
};

export type MarketSeriesHistoryResponse = {
  symbol: string;
  name: string;
  series_type: "index" | "industry";
  range: MarketIndexWindow;
  point_count: number;
  required_points: number | null;
  points: MarketIndexHistoryPoint[];
  source: string;
  as_of: string | null;
  updated_at: string | null;
  expires_at: string | null;
  stale: boolean;
  fallback_used: boolean;
  fallback_reason?: string | null;
  data_quality_grade: string;
  warnings: Array<{ code: string; severity: string; message: string }>;
  not_production_model: boolean;
  main_score_changed: boolean;
  main_risk_changed: boolean;
};

export type MarketIndexHistoryResponse = Omit<
  MarketSeriesHistoryResponse,
  "series_type"
> & {
  series_type: "index";
};

export type MarketSectorHistoryResponse = Omit<
  MarketSeriesHistoryResponse,
  "series_type"
> & {
  series_type: "industry";
};

export type MarketSectorItem = {
  symbol: string;
  name: string;
  entity_type: "industry";
  latest: number | null;
  change_pct: number | null;
  market_cap?: number | null;
  turnover_rate?: number | null;
  rise_count?: number | null;
  fall_count?: number | null;
  leader_name?: string | null;
  leader_change_pct?: number | null;
  source: string;
  as_of: string | null;
  updated_at?: string | null;
  expires_at?: string | null;
  stale: boolean;
};

export type MarketSectorSearchParams = {
  q?: string;
  page?: number;
  pageSize?: number;
};

export type MarketSectorSearchResponse = {
  items: MarketSectorItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  query: string;
  sort: string;
  source: string | null;
  as_of: string | null;
  updated_at?: string | null;
  expires_at?: string | null;
  stale: boolean;
  fallback_used: boolean;
  fallback_reason?: string | null;
  data_quality_grade: string;
  warnings: Array<{ code: string; severity: string; message: string }>;
  not_production_model: boolean;
  main_score_changed: boolean;
  main_risk_changed: boolean;
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

export type FundSearchItem = {
  code: string;
  name: string;
  fund_type: string;
  primary_theme: string;
  themes: string[];
  classification_confidence: number | null;
  nav: number | null;
  scale: number | null;
  exchange_traded: boolean;
  returns: Partial<Record<"1m" | "3m" | "6m" | "1y", number>>;
  source: string;
  as_of: string | null;
  valuation_date: string | null;
  updated_at: string | null;
  expires_at: string | null;
  stale: boolean;
  data_quality_grade: string;
};

export type FundSearchParams = {
  q?: string;
  fundType?: string;
  theme?: string;
  exchangeTraded?: boolean;
  quality?: "normal" | "warning" | "degraded" | "unknown";
  sort?: "code" | "name" | "return_1m" | "return_3m" | "return_6m" | "return_1y";
  direction?: "asc" | "desc";
  page?: number;
  pageSize?: number;
};

export type FundSearchResponse = {
  availability: Availability;
  items: FundSearchItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  facets: {
    fund_types: Record<string, number>;
    themes: Record<string, number>;
    exchange_traded: Record<string, number>;
    qualities: Record<string, number>;
  };
  as_of: string | null;
  source: string | null;
  data_quality_grade: string;
  index_stale: boolean;
  warnings: string[];
};

export type ProductFundSummary = {
  code: string | null;
  name: string | null;
  fund_type: string | null;
  primary_theme: string | null;
  themes: string[];
  nav: number | null;
  scale: number | null;
  exchange_traded: boolean;
  returns: Partial<Record<"1m" | "3m" | "6m" | "1y", number | null>>;
  data_date: string | null;
  data_status: ProductDataStatus;
};

export type ProductFundSearchResponse = {
  availability: Availability;
  items: ProductFundSummary[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  facets: {
    fund_types: Record<string, number>;
    themes: Record<string, number>;
    exchange_traded: Record<string, number>;
    data_states: Record<string, number>;
  };
  data_date: string | null;
  data_status: ProductDataStatus;
};

export type FundResearchDetail = Pick<
  FundDetailItem,
  | "fund_company"
  | "fund_manager"
  | "inception_date"
  | "rating"
  | "data_quality_grade"
  | "data_quality_warnings"
  | "missing_fields"
  | "return_windows"
  | "data_coverage"
  | "signal_context"
> & {
  accumulated_nav?: number | null;
  market_rank_context?: Record<string, unknown>;
  nav_history_summary?: Record<string, unknown>;
  observation_notes?: string[];
  peer_comparison?: Record<string, unknown>;
  unknown_reason?: string;
  is_watchlist?: boolean;
  is_portfolio?: boolean;
};

export type FundDetailResponse = {
  fund: FundSearchItem;
  research_detail: FundResearchDetail;
  not_production_model: boolean;
  main_score_changed: boolean;
  main_risk_changed: boolean;
};

export type ProductFundResearchDetail = {
  fund_company: string | null;
  fund_manager: string | null;
  inception_date: string | null;
  rating: string | number | null;
  accumulated_nav: number | null;
  return_windows: Record<string, { total_return: number | null; max_drawdown: number | null; volatility: number | null }>;
  coverage: { coverage_ratio: number | null; label: string };
  missing_fields: string[];
  is_watchlist: boolean;
  is_portfolio: boolean;
  data_status: ProductDataStatus;
};

export type ProductFundDetailResponse = {
  fund: ProductFundSummary;
  research: ProductFundResearchDetail;
};

export type ProductFundProfileOverview = {
  full_name: string | null;
  fund_company: string | null;
  custodian: string | null;
  fund_manager: string | null;
  issue_date: string | null;
  inception_date: string | null;
  asset_scale: number | null;
  asset_scale_unit: string | null;
  share_scale: number | null;
  share_scale_unit: string | null;
  benchmark: string | null;
  tracking_target: string | null;
};

export type ProductFundTradingRule = {
  purchase_status: string | null;
  redemption_status: string | null;
  next_open_date: string | null;
  minimum_purchase_amount: string | null;
  daily_purchase_limit: string | null;
  confirmation_rule: string | null;
};

export type ProductFundFee = {
  fee_type: string | null;
  condition: string | null;
  period: string | null;
  channel: string | null;
  original_rate: string | null;
  discounted_rate: string | null;
};

export type ProductFundProfileResponse = {
  fund: { code: string; name: string | null; fund_type: string | null };
  profile: ProductFundProfileOverview | null;
  trading_rule: ProductFundTradingRule | null;
  fees: ProductFundFee[];
  data_status: ProductDataStatus;
  component_status: {
    profile: ProductDataStatus;
    trading_rule: ProductDataStatus;
    fees: ProductDataStatus;
  };
};

export type FundHistoryWindow = "1m" | "3m" | "6m" | "1y" | "all";

export type FundHistoryPoint = {
  date: string;
  unit_nav: number | null;
  accumulated_nav: number | null;
  daily_return: number | null;
  source: string;
};

export type FundHistoryResponse = {
  code: string;
  range: FundHistoryWindow;
  point_count: number;
  required_points: number | null;
  points: FundHistoryPoint[];
  source: string;
  as_of: string | null;
  updated_at: string | null;
  expires_at: string | null;
  stale: boolean;
  fallback_used: boolean;
  fallback_reason?: string | null;
  data_quality_grade: string;
  warnings: Array<{ code: string; severity: string; message: string }>;
  not_production_model: boolean;
  main_score_changed: boolean;
  main_risk_changed: boolean;
};

export type ProductFundHistoryPoint = {
  date: string | null;
  unit_nav: number | null;
  accumulated_nav: number | null;
  daily_return: number | null;
};

export type ProductFundHistoryResponse = {
  code: string | null;
  range: FundHistoryWindow;
  point_count: number;
  required_points: number | null;
  points: ProductFundHistoryPoint[];
  data_date: string | null;
  data_status: ProductDataStatus;
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
  valued_total_value?: number | null;
  valuation_status?: "complete" | "partial" | "unavailable" | "not_configured" | string | null;
  valued_position_count?: number;
  unvalued_position_count?: number;
  cash_available?: number | null;
  total_unrealized_return_pct?: number | null;
  positions?: PortfolioPosition[];
  theme_exposure?: Record<string, { holding_count?: number; current_value?: number | null; weight?: number | null }>;
  fund_type_exposure?: Record<string, { holding_count?: number; current_value?: number | null; weight?: number | null }>;
  observation_issues?: Array<{ issue_type?: string; severity?: string; message?: string; metadata?: Record<string, unknown> }>;
  warnings?: string[];
};

export type ProductWatchlistFund = {
  code: string | null;
  name: string | null;
  fund_type: string | null;
  primary_theme: string | null;
  nav: number | null;
  return_windows: Record<string, { total_return: number | null; max_drawdown: number | null; volatility: number | null }>;
  coverage_ratio: number | null;
  data_status: ProductDataStatus;
};

export type ProductWatchlistData = {
  as_of: string | null;
  funds: ProductWatchlistFund[];
  detail_count: number;
  coverage_ratio: number | null;
  data_status: ProductDataStatus;
};

export type ProductPortfolioPosition = {
  code: string | null;
  name: string | null;
  shares: number | null;
  cost_value: number | null;
  current_value: number | null;
  unrealized_return_pct: number | null;
  weight: number | null;
  primary_theme: string | null;
};

export type ProductPortfolioData = {
  as_of: string | null;
  portfolio_name: string | null;
  holding_count: number;
  cash_available: number | null;
  total_value: number | null;
  valued_total_value: number | null;
  total_unrealized_return_pct: number | null;
  valuation: {
    state: string;
    label: string;
    description: string;
    valued_position_count: number | null;
    unvalued_position_count: number | null;
  };
  positions: ProductPortfolioPosition[];
  theme_exposure: Record<string, { holding_count?: number; current_value?: number | null; weight?: number | null; codes?: string[] }>;
  fund_type_exposure: Record<string, { holding_count?: number; current_value?: number | null; weight?: number | null; codes?: string[] }>;
  observations: Array<{ tone: string; title: string; description: string }>;
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
  indexed_fund_codes?: string[];
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
