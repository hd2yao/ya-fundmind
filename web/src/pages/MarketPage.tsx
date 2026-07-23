import { ArrowDownRight, ArrowUpRight, History, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { getMarketIndexHistory } from "../api/client";
import type {
  MarketData,
  MarketIndexHistoryResponse,
  MarketIndexWindow,
  ThemeSummary
} from "../api/types";
import { EvidenceDrawer } from "../components/EvidenceDrawer";
import { MarketIndexChart } from "../components/MarketIndexChart";
import { Metric } from "../components/Metric";
import { PageHeader } from "../components/PageHeader";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge, type StatusTone } from "../components/StatusBadge";
import { TrendChart } from "../components/TrendChart";
import { useApiResource } from "../hooks/useApiResource";

const number = new Intl.NumberFormat("zh-CN");
const indexNumber = new Intl.NumberFormat("zh-CN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
});
const INDEX_OPTIONS = [
  { symbol: "000001", name: "上证指数" },
  { symbol: "000300", name: "沪深300" },
  { symbol: "399006", name: "创业板指" }
] as const;
const INDEX_WINDOWS: Array<{ value: MarketIndexWindow; label: string }> = [
  { value: "1m", label: "1 月" },
  { value: "3m", label: "3 月" },
  { value: "6m", label: "6 月" },
  { value: "1y", label: "1 年" },
  { value: "all", label: "全部" }
];

type IndexHistoryState = {
  loading: boolean;
  data: MarketIndexHistoryResponse | null;
  error: string | null;
};

function formatReturn(value?: number | null) {
  if (value === null || value === undefined) return "--";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function qualityTone(grade?: string | null): StatusTone {
  if (grade === "normal" || grade === "success") return "success";
  if (grade === "warning") return "warning";
  if (grade === "degraded" || grade === "critical") return "critical";
  return "neutral";
}

export function MarketPage() {
  const { loading, resource, error } = useApiResource<MarketData>("/api/market");
  const [selectedTheme, setSelectedTheme] = useState<ThemeSummary | null>(null);
  const [selectedIndex, setSelectedIndex] = useState("000300");
  const [indexWindow, setIndexWindow] = useState<MarketIndexWindow>("6m");
  const [indexHistory, setIndexHistory] = useState<IndexHistoryState>({
    loading: true,
    data: null,
    error: null
  });

  const topThemes = useMemo(() => resource?.data.intelligence?.top_themes || [], [resource]);

  useEffect(() => {
    const controller = new AbortController();
    setIndexHistory({ loading: true, data: null, error: null });
    getMarketIndexHistory(selectedIndex, indexWindow, controller.signal)
      .then((data) => setIndexHistory({ loading: false, data, error: null }))
      .catch((historyError: unknown) => {
        if (controller.signal.aborted) return;
        setIndexHistory({
          loading: false,
          data: null,
          error: historyError instanceof Error
            ? historyError.message
            : "指数历史读取失败。"
        });
      });
    return () => controller.abort();
  }, [selectedIndex, indexWindow]);

  if (loading) {
    return <StatePanel kind="loading" title="正在读取市场情报" description="加载全市场分类、主题窗口和历史趋势。" />;
  }
  if (error) {
    return <StatePanel kind="error" title="市场情报读取失败" description={error} />;
  }
  if (!resource || resource.availability === "missing") {
    return (
      <StatePanel
        kind="empty"
        title="尚无市场情报产物"
        description="运行 daily ops 并开启 ENABLE_MARKET_INTELLIGENCE=true 后再查看。"
      />
    );
  }

  const intelligence = resource.data.intelligence || {};
  const trend = resource.data.trend || {};
  const quality = intelligence.data_quality_summary?.grade || "unknown";
  const persistent = trend.persistent_hot_themes || [];
  const newThemes = trend.new_hot_themes || [];
  const rising = trend.rising_themes || [];

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Market intelligence"
        title="市场情报"
        description="全市场观察与历史趋势验证，不等同于自选池，也不构成板块推荐。"
        actions={<StatusBadge tone={qualityTone(quality)}>{quality}</StatusBadge>}
      />

      <section className="metric-grid" aria-label="市场覆盖指标">
        <Metric label="基金覆盖" value={number.format(intelligence.total_funds || 0)} detail={`as_of ${intelligence.as_of || "--"}`} />
        <Metric label="ETF 覆盖" value={number.format(intelligence.total_etfs || 0)} detail={`source ${intelligence.source || "--"}`} />
        <Metric label="趋势快照" value={trend.snapshots_processed || 0} detail={trend.enough_market_history ? "历史样本已满足" : "历史样本不足"} />
        <Metric label="持续热点" value={persistent.length} detail={`新出现 ${newThemes.length}`} />
      </section>

      <IndexHistoryPanel
        state={indexHistory}
        symbol={selectedIndex}
        window={indexWindow}
        onSymbolChange={setSelectedIndex}
        onWindowChange={setIndexWindow}
      />

      <section className="content-band" aria-labelledby="top-theme-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Observed themes</p>
            <h2 id="top-theme-title">主题窗口对比</h2>
          </div>
          <span className="section-meta">仅展示既有计算结果</span>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>主题</th>
                <th>1 周</th>
                <th>1 月</th>
                <th>3 月</th>
                <th>正收益占比</th>
                <th>样本</th>
                <th>质量</th>
                <th aria-label="操作" />
              </tr>
            </thead>
            <tbody>
              {topThemes.slice(0, 12).map((theme) => (
                <tr key={theme.theme}>
                  <td><strong>{theme.theme || "未分类"}</strong></td>
                  <td className={Number(theme.avg_return_1w) >= 0 ? "number-positive" : "number-negative"}>{formatReturn(theme.avg_return_1w)}</td>
                  <td className={Number(theme.avg_return_1m) >= 0 ? "number-positive" : "number-negative"}>{formatReturn(theme.avg_return_1m)}</td>
                  <td className={Number(theme.avg_return_3m) >= 0 ? "number-positive" : "number-negative"}>{formatReturn(theme.avg_return_3m)}</td>
                  <td>{theme.positive_ratio_1m == null ? "--" : `${(theme.positive_ratio_1m * 100).toFixed(1)}%`}</td>
                  <td>{number.format(theme.sample_size || 0)}</td>
                  <td><StatusBadge tone={qualityTone(theme.data_quality_grade)}>{theme.data_quality_grade || "unknown"}</StatusBadge></td>
                  <td>
                    <button className="table-action" type="button" aria-label={`查看${theme.theme || "未分类"}详情`} onClick={() => setSelectedTheme(theme)}>
                      查看
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="split-grid">
        <section className="content-band" aria-labelledby="trend-title">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Data quality history</p>
              <h2 id="trend-title">质量趋势</h2>
            </div>
            <History size={19} aria-hidden />
          </div>
          <TrendChart data={trend.data_quality_trend || []} />
        </section>

        <section className="content-band" aria-labelledby="movement-title">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Theme movement</p>
              <h2 id="movement-title">近期变化</h2>
            </div>
            <Sparkles size={19} aria-hidden />
          </div>
          <div className="movement-list">
            {rising.slice(0, 4).map((item) => (
              <div className="movement-item" key={`rise-${item.theme}`}>
                <ArrowUpRight className="number-positive" size={18} aria-hidden />
                <strong>{item.theme || "未分类"}</strong>
                <span>排名 +{item.rank_change ?? 0}</span>
              </div>
            ))}
            {newThemes.slice(0, 4).map((item) => (
              <div className="movement-item" key={`new-${item.theme}`}>
                <Sparkles className="number-positive" size={18} aria-hidden />
                <strong>{item.theme || "未分类"}</strong>
                <span>新进入观察</span>
              </div>
            ))}
            {(trend.falling_themes || []).slice(0, 2).map((item) => (
              <div className="movement-item" key={`fall-${item.theme}`}>
                <ArrowDownRight className="number-negative" size={18} aria-hidden />
                <strong>{item.theme || "未分类"}</strong>
                <span>排名 {item.rank_change ?? 0}</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="notice notice--info">
        <History size={18} aria-hidden />
        <div>
          <strong>全市场观察，不是自选或持仓建议</strong>
          <p>主题收益、排名和热度只用于研究验证。样本不足、warning 或 stale 数据必须结合详情人工复核。</p>
        </div>
      </div>

      <EvidenceDrawer
        open={selectedTheme !== null}
        title={`${selectedTheme?.theme || "未分类"}观察详情`}
        onClose={() => setSelectedTheme(null)}
      >
        {selectedTheme ? (
          <dl className="detail-list">
            <div><dt>1 周平均</dt><dd>{formatReturn(selectedTheme.avg_return_1w)}</dd></div>
            <div><dt>1 月平均</dt><dd>{formatReturn(selectedTheme.avg_return_1m)}</dd></div>
            <div><dt>3 月平均</dt><dd>{formatReturn(selectedTheme.avg_return_3m)}</dd></div>
            <div><dt>有效样本</dt><dd>样本 {number.format(selectedTheme.sample_size || 0)}</dd></div>
            <div><dt>数据质量</dt><dd>{selectedTheme.data_quality_grade || "unknown"}</dd></div>
            <div><dt>as_of</dt><dd>{intelligence.as_of || "--"}</dd></div>
            <div><dt>source</dt><dd>{intelligence.source || "--"}</dd></div>
          </dl>
        ) : null}
      </EvidenceDrawer>
    </div>
  );
}

function IndexHistoryPanel({
  state,
  symbol,
  window,
  onSymbolChange,
  onWindowChange
}: {
  state: IndexHistoryState;
  symbol: string;
  window: MarketIndexWindow;
  onSymbolChange: (symbol: string) => void;
  onWindowChange: (window: MarketIndexWindow) => void;
}) {
  const latest = state.data?.points.at(-1);
  return (
    <section className="content-band market-index-panel" aria-labelledby="market-index-title">
      <div className="market-index-toolbar">
        <div>
          <p className="eyebrow">Market indices</p>
          <h2 id="market-index-title">主要指数走势</h2>
        </div>
        <div className="market-index-controls">
          <div className="index-symbol-tabs" aria-label="主要指数">
            {INDEX_OPTIONS.map((item) => (
              <button
                key={item.symbol}
                type="button"
                aria-label={item.name}
                aria-pressed={symbol === item.symbol}
                className={symbol === item.symbol ? "index-tab index-tab--active" : "index-tab"}
                onClick={() => onSymbolChange(item.symbol)}
              >
                {item.name}
              </button>
            ))}
          </div>
          <div className="history-window-tabs" aria-label="指数历史时间范围">
            {INDEX_WINDOWS.map((item) => (
              <button
                key={item.value}
                type="button"
                aria-label={item.label}
                aria-pressed={window === item.value}
                className={window === item.value ? "history-window history-window--active" : "history-window"}
                onClick={() => onWindowChange(item.value)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </div>
      {state.loading ? (
        <StatePanel kind="loading" title="正在读取指数日线" description="优先使用本地缓存，缺失时按需读取 AKShare。" />
      ) : null}
      {state.error ? (
        <StatePanel kind="error" title="指数日线暂不可用" description={state.error} />
      ) : null}
      {state.data && state.data.points.length ? (
        <>
          <div className="market-index-summary">
            <div>
              <span>{state.data.name}</span>
              <strong>{indexNumber.format(latest?.close || 0)}</strong>
            </div>
            <div>
              <span>日涨跌</span>
              <strong className={Number(latest?.change_pct) >= 0 ? "number-positive" : "number-negative"}>
                {formatReturn(latest?.change_pct)}
              </strong>
            </div>
            <div>
              <span>样本</span>
              <strong>{state.data.point_count} 个交易点</strong>
            </div>
            <div>
              <span>来源 / 截至</span>
              <strong>{state.data.source} · {state.data.as_of || "--"}</strong>
            </div>
          </div>
          <MarketIndexChart name={state.data.name} points={state.data.points} />
          <div className="status-row">
            <StatusBadge tone={qualityTone(state.data.data_quality_grade)}>
              {state.data.stale ? "stale" : state.data.data_quality_grade}
            </StatusBadge>
            {state.data.fallback_used ? <StatusBadge tone="warning">cache fallback</StatusBadge> : null}
          </div>
          {state.data.warnings.length ? (
            <p className="history-warning">
              {state.data.warnings.map((warning) => warning.message).join(" · ")}
            </p>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
