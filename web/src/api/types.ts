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
