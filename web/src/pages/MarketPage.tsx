import { ArrowDownRight, ArrowUpRight, History, RefreshCw, Search, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  getMarketIndexHistory,
  getMarketSectorHistory,
  searchMarketSectors
} from "../api/client";
import type {
  MarketData,
  MarketIndexHistoryResponse,
  MarketIndexWindow,
  MarketSectorHistoryResponse,
  MarketSectorItem,
  MarketSectorSearchResponse,
  ThemeSummary
} from "../api/types";
import { getDataCondition } from "../components/DataFreshnessStrip";
import { MarketIndexChart } from "../components/MarketIndexChart";
import { Metric } from "../components/Metric";
import { PageHeader } from "../components/PageHeader";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge, type StatusTone } from "../components/StatusBadge";
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

type SectorCatalogState = {
  loading: boolean;
  data: MarketSectorSearchResponse | null;
  error: string | null;
};

type SectorHistoryState = {
  loading: boolean;
  data: MarketSectorHistoryResponse | null;
  error: string | null;
};

function formatReturn(value?: number | null) {
  if (value === null || value === undefined) return "--";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function returnClass(value?: number | null) {
  if (value === null || value === undefined || value === 0) return "number-neutral";
  return value > 0 ? "number-positive" : "number-negative";
}

function themeReadiness(theme: ThemeSummary): { label: string; tone: StatusTone } {
  if (theme.data_quality_grade === "critical" || theme.data_quality_grade === "degraded") {
    return { label: "样本不足", tone: "critical" };
  }
  if (theme.data_quality_grade === "warning") {
    return { label: "样本较少", tone: "warning" };
  }
  if (theme.sample_size === null || theme.sample_size === undefined) {
    return { label: "待补充", tone: "neutral" };
  }
  return { label: "数据充分", tone: "success" };
}

export function MarketPage() {
  const { loading, resource, error, refresh, refreshVersion } = useApiResource<MarketData>("/api/market");
  const [selectedIndex, setSelectedIndex] = useState("000300");
  const [indexWindow, setIndexWindow] = useState<MarketIndexWindow>("6m");
  const [indexHistory, setIndexHistory] = useState<IndexHistoryState>({
    loading: true,
    data: null,
    error: null
  });
  const [sectorQuery, setSectorQuery] = useState("");
  const [appliedSectorQuery, setAppliedSectorQuery] = useState("");
  const [sectorCatalog, setSectorCatalog] = useState<SectorCatalogState>({
    loading: true,
    data: null,
    error: null
  });
  const [selectedSector, setSelectedSector] = useState<MarketSectorItem | null>(null);
  const [sectorWindow, setSectorWindow] = useState<MarketIndexWindow>("6m");
  const [sectorHistory, setSectorHistory] = useState<SectorHistoryState>({
    loading: false,
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
  }, [selectedIndex, indexWindow, refreshVersion]);

  useEffect(() => {
    const controller = new AbortController();
    setSectorCatalog({ loading: true, data: null, error: null });
    searchMarketSectors(
      {
        q: appliedSectorQuery,
        page: 1,
        pageSize: 12
      },
      controller.signal
    )
      .then((data) => {
        setSectorCatalog({ loading: false, data, error: null });
        setSelectedSector((current) => {
          const retained = current
            ? data.items.find((item) => item.symbol === current.symbol)
            : null;
          return retained || data.items[0] || null;
        });
      })
      .catch((catalogError: unknown) => {
        if (controller.signal.aborted) return;
        setSectorCatalog({
          loading: false,
          data: null,
          error: catalogError instanceof Error
            ? catalogError.message
            : "行业板块目录读取失败。"
        });
        setSelectedSector(null);
      });
    return () => controller.abort();
  }, [appliedSectorQuery, refreshVersion]);

  useEffect(() => {
    if (!selectedSector) {
      setSectorHistory({ loading: false, data: null, error: null });
      return;
    }
    const controller = new AbortController();
    setSectorHistory({ loading: true, data: null, error: null });
    getMarketSectorHistory(
      selectedSector.symbol,
      sectorWindow,
      controller.signal
    )
      .then((data) => setSectorHistory({ loading: false, data, error: null }))
      .catch((historyError: unknown) => {
        if (controller.signal.aborted) return;
        setSectorHistory({
          loading: false,
          data: null,
          error: historyError instanceof Error
            ? historyError.message
            : "行业板块历史读取失败。"
        });
      });
    return () => controller.abort();
  }, [selectedSector, sectorWindow, refreshVersion]);

  const sectorPanel = (
    <SectorMarketPanel
      catalog={sectorCatalog}
      history={sectorHistory}
      query={sectorQuery}
      selectedSector={selectedSector}
      window={sectorWindow}
      onQueryChange={setSectorQuery}
      onSearch={() => setAppliedSectorQuery(sectorQuery.trim())}
      onSectorChange={setSelectedSector}
      onWindowChange={setSectorWindow}
    />
  );

  if (loading && !resource) {
    return <StatePanel kind="loading" title="正在读取市场情报" description="加载全市场分类、主题窗口和历史趋势。" />;
  }
  if (error) {
    return <StatePanel kind="error" title="市场情报读取失败" description={error} />;
  }
  if (!resource || resource.availability === "missing") {
    return (
      <div className="page-stack">
        <PageHeader
          eyebrow="Market terminal"
          title="行情总览"
          description="主要指数可独立按需读取；主题与趋势仍依赖每日 Market Intelligence 产物。"
          actions={<StatusBadge tone="neutral">index only</StatusBadge>}
        />
        <IndexHistoryPanel
          state={indexHistory}
          symbol={selectedIndex}
          window={indexWindow}
          onSymbolChange={setSelectedIndex}
          onWindowChange={setIndexWindow}
        />
        {sectorPanel}
        <StatePanel
          kind="empty"
          title="尚无市场情报产物"
          description="指数浏览仍可使用；运行 daily ops 并开启 ENABLE_MARKET_INTELLIGENCE=true 后生成主题与趋势。"
        />
      </div>
    );
  }

  const intelligence = resource.data.intelligence || {};
  const trend = resource.data.trend || {};
  const marketCondition = getDataCondition({
    dataQualityGrade: intelligence.data_quality_summary?.grade
  });
  const persistent = trend.persistent_hot_themes || [];
  const newThemes = trend.new_hot_themes || [];
  const rising = trend.rising_themes || [];

  function searchMatchingSector(themeName: string) {
    setSectorQuery(themeName);
    setAppliedSectorQuery(themeName);
    globalThis.document
      ?.getElementById("market-sector-title")
      ?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  }

  return (
    <div className="page-stack market-workbench">
      <PageHeader
        eyebrow="市场总览"
        title="行情总览"
        description="浏览主要指数、行业板块和主题变化；全市场数据不等同于自选基金。"
        actions={
          <div className="market-page-actions">
            <button className="workspace-refresh-button" type="button" onClick={refresh} disabled={loading}>
              <RefreshCw className={loading ? "is-spinning" : undefined} size={15} aria-hidden />
              刷新行情
            </button>
          </div>
        }
      />

      <nav className="terminal-section-nav" aria-label="行情数据区域">
        <a href="#market-index">主要指数</a>
        <a href="#market-sector-title">行业板块</a>
        <a href="#top-theme-title">主题窗口</a>
      </nav>

      <section className="market-pulse" aria-label="市场数据脉冲">
        <div className="market-pulse__intro">
          <span>市场快照</span>
          <strong>交易数据日期</strong>
          <b>{intelligence.as_of || "--"}</b>
        </div>
        <div className="market-pulse__fact">
          <span>更新于</span>
          <strong>{formatDateTime(resource.generated_at)}</strong>
        </div>
        <div className="market-pulse__fact">
          <span>覆盖范围</span>
          <strong>全市场基金与 ETF</strong>
        </div>
        <div className="market-pulse__fact">
          <span>数据状态</span>
          <StatusBadge tone={marketCondition.tone}>{marketCondition.label}</StatusBadge>
        </div>
      </section>

      <section className="metric-grid market-coverage-rail" aria-label="市场覆盖指标">
        <Metric label="基金覆盖" value={number.format(intelligence.total_funds || 0)} detail="全市场基础索引" />
        <Metric label="ETF 覆盖" value={number.format(intelligence.total_etfs || 0)} detail="可进入基金终端搜索" />
        <Metric label="主题观察" value={topThemes.length} detail="按基金主题汇总" />
        <Metric label="近期变化" value={persistent.length + newThemes.length} detail={`持续关注 ${persistent.length}`} />
      </section>

      <IndexHistoryPanel
        state={indexHistory}
        symbol={selectedIndex}
        window={indexWindow}
        onSymbolChange={setSelectedIndex}
        onWindowChange={setIndexWindow}
      />

      {sectorPanel}

      <section className="content-band" aria-labelledby="top-theme-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">主题观察</p>
            <h2 id="top-theme-title">主题窗口对比</h2>
          </div>
          <span className="section-meta">截至 {intelligence.as_of || "--"}</span>
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
                <th>解读提示</th>
                <th aria-label="操作" />
              </tr>
            </thead>
            <tbody>
              {topThemes.slice(0, 12).map((theme) => {
                const readiness = themeReadiness(theme);
                return (
                <tr key={theme.theme}>
                  <td><strong>{theme.theme || "未分类"}</strong></td>
                  <td className={returnClass(theme.avg_return_1w)}>{formatReturn(theme.avg_return_1w)}</td>
                  <td className={returnClass(theme.avg_return_1m)}>{formatReturn(theme.avg_return_1m)}</td>
                  <td className={returnClass(theme.avg_return_3m)}>{formatReturn(theme.avg_return_3m)}</td>
                  <td>{theme.positive_ratio_1m == null ? "--" : `${(theme.positive_ratio_1m * 100).toFixed(1)}%`}</td>
                  <td>{number.format(theme.sample_size || 0)}</td>
                  <td><StatusBadge tone={readiness.tone}>{readiness.label}</StatusBadge></td>
                  <td>
                    <div className="table-action-group">
                      {theme.theme ? (
                        <button
                          className="table-action table-action--search"
                          type="button"
                          aria-label={`搜索${theme.theme}同名行业板块`}
                          title="查看同名行业板块"
                          onClick={() => searchMatchingSector(theme.theme || "")}
                        >
                          <Search size={13} aria-hidden />
                          查看板块
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="content-band market-movement-panel" aria-labelledby="movement-title">
          <div className="section-heading">
            <div>
            <p className="eyebrow">主题变化</p>
              <h2 id="movement-title">近期变化</h2>
            </div>
            <Sparkles size={19} aria-hidden />
          </div>
          <div className="movement-list">
            {rising.slice(0, 4).map((item) => (
              <button className="movement-item movement-item--interactive" type="button" key={`rise-${item.theme}`} onClick={() => searchMatchingSector(item.theme || "")}>
                <ArrowUpRight className="number-positive" size={18} aria-hidden />
                <strong>{item.theme || "未分类"}</strong>
                <span>排名 +{item.rank_change ?? 0}</span>
              </button>
            ))}
            {newThemes.slice(0, 4).map((item) => (
              <button className="movement-item movement-item--interactive" type="button" key={`new-${item.theme}`} onClick={() => searchMatchingSector(item.theme || "")}>
                <Sparkles className="number-positive" size={18} aria-hidden />
                <strong>{item.theme || "未分类"}</strong>
                <span>新进入观察</span>
              </button>
            ))}
            {(trend.falling_themes || []).slice(0, 2).map((item) => (
              <button className="movement-item movement-item--interactive" type="button" key={`fall-${item.theme}`} onClick={() => searchMatchingSector(item.theme || "")}>
                <ArrowDownRight className="number-negative" size={18} aria-hidden />
                <strong>{item.theme || "未分类"}</strong>
                <span>排名 {item.rank_change ?? 0}</span>
              </button>
            ))}
          </div>
      </section>

      <div className="notice notice--info">
        <History size={18} aria-hidden />
        <div>
          <strong>全市场观察，不是自选或持仓建议</strong>
          <p>主题收益、排名和热度只用于研究观察。页面会将样本不足或更新待确认的信息明确标出，请结合基金详情人工复核。</p>
        </div>
      </div>
    </div>
  );
}

function SectorMarketPanel({
  catalog,
  history,
  query,
  selectedSector,
  window,
  onQueryChange,
  onSearch,
  onSectorChange,
  onWindowChange
}: {
  catalog: SectorCatalogState;
  history: SectorHistoryState;
  query: string;
  selectedSector: MarketSectorItem | null;
  window: MarketIndexWindow;
  onQueryChange: (query: string) => void;
  onSearch: () => void;
  onSectorChange: (sector: MarketSectorItem) => void;
  onWindowChange: (window: MarketIndexWindow) => void;
}) {
  const latest = history.data?.points.at(-1);
  const catalogCondition = catalog.data
    ? getDataCondition({
        stale: catalog.data.stale,
        fallbackUsed: catalog.data.fallback_used,
        dataQualityGrade: catalog.data.data_quality_grade
      })
    : null;
  const historyCondition = history.data
    ? getDataCondition({
        stale: history.data.stale,
        fallbackUsed: history.data.fallback_used,
        dataQualityGrade: history.data.data_quality_grade
      })
    : null;
  return (
    <section className="content-band market-sector-panel" aria-labelledby="market-sector-title">
      <div className="market-sector-toolbar">
        <div>
            <p className="eyebrow">行业板块</p>
          <h2 id="market-sector-title">行业板块行情</h2>
          <p className="section-description">
            按当日涨跌幅排序，可搜索板块名称或 BK 代码。
          </p>
        </div>
        <form
          className="market-sector-search"
          onSubmit={(event) => {
            event.preventDefault();
            onSearch();
          }}
        >
          <label htmlFor="market-sector-query">搜索行业板块</label>
          <div>
            <input
              id="market-sector-query"
              type="search"
              value={query}
              placeholder="例如：半导体 / BK1036"
              onChange={(event) => onQueryChange(event.target.value)}
            />
            <button
              className="secondary-button"
              type="submit"
              aria-label="搜索板块"
            >
              <Search size={16} aria-hidden />
              搜索
            </button>
          </div>
        </form>
      </div>

      {catalog.loading ? (
        <StatePanel
          kind="loading"
          title="正在读取行业板块目录"
          description="正在加载可浏览的行业板块。"
        />
      ) : null}
      {catalog.error ? (
        <StatePanel
          kind="error"
          title="行业板块目录暂不可用"
          description="暂时无法读取板块列表，请稍后刷新页面。"
        />
      ) : null}
      {catalog.data && !catalog.data.items.length ? (
        <StatePanel
          kind="empty"
          title="没有匹配的行业板块"
          description="请尝试完整板块名称或 BK 开头的板块代码。"
        />
      ) : null}

      {catalog.data?.items.length ? (
        <div className="market-sector-workspace">
          <div className="market-sector-directory">
            <div className="market-sector-directory__meta">
              <span>共 {catalog.data.total} 个板块，当前显示 {catalog.data.items.length} 条</span>
            </div>
            <div className="table-wrap market-sector-table">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>板块</th>
                    <th>最新</th>
                    <th>日涨跌</th>
                    <th>上涨 / 下跌</th>
                    <th>领涨股票</th>
                  </tr>
                </thead>
                <tbody>
                  {catalog.data.items.map((sector) => (
                    <tr
                      key={sector.symbol}
                      className={
                        selectedSector?.symbol === sector.symbol
                          ? "market-sector-row market-sector-row--active"
                          : "market-sector-row"
                      }
                      tabIndex={0}
                      onClick={() => onSectorChange(sector)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          onSectorChange(sector);
                        }
                      }}
                    >
                      <td>
                        <button
                          className="market-sector-select"
                          type="button"
                          aria-label={`查看${sector.name}走势`}
                          aria-pressed={selectedSector?.symbol === sector.symbol}
                          onClick={(event) => {
                            event.stopPropagation();
                            onSectorChange(sector);
                          }}
                        >
                          <strong>{sector.name}</strong>
                          <span>{sector.symbol}</span>
                        </button>
                      </td>
                      <td>{sector.latest == null ? "--" : indexNumber.format(sector.latest)}</td>
                      <td className={returnClass(sector.change_pct)}>
                        {formatReturn(sector.change_pct)}
                      </td>
                      <td>{sector.rise_count ?? "--"} / {sector.fall_count ?? "--"}</td>
                      <td>{sector.leader_name || "--"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {catalogCondition?.message ? <p className="market-data-note">{catalogCondition.message}</p> : null}
          </div>

          <div className="market-sector-history">
            <div className="market-sector-history__header">
              <div>
                <span>已选板块</span>
                <strong>
                  {selectedSector?.name || "--"}
                </strong>
              </div>
              <div className="history-window-tabs" aria-label="板块历史时间范围">
                {INDEX_WINDOWS.map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    aria-label={`板块 ${item.label}`}
                    aria-pressed={window === item.value}
                    className={window === item.value ? "history-window history-window--active" : "history-window"}
                    onClick={() => onWindowChange(item.value)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
            {history.loading ? (
              <StatePanel
                kind="loading"
                title="正在读取板块日线"
                description="正在加载所选板块的历史走势。"
              />
            ) : null}
            {history.error ? (
              <StatePanel
                kind="error"
                title="板块日线暂不可用"
                description="该板块暂未形成可展示的历史走势，请选择其他板块或稍后再查看。"
              />
            ) : null}
            {history.data && history.data.points.length ? (
              <>
                <div className="market-index-summary market-index-summary--compact">
                  <div>
                    <span>{history.data.name}</span>
                    <strong>{latest?.close == null ? "--" : indexNumber.format(latest.close)}</strong>
                  </div>
                  <div>
                    <span>当日涨跌</span>
                    <strong className={returnClass(latest?.change_pct)}>
                      {formatReturn(latest?.change_pct)}
                    </strong>
                  </div>
                  <div>
                    <span>样本</span>
                    <strong>{history.data.point_count} 个交易点</strong>
                  </div>
                  <div>
                    <span>数据日期</span>
                    <strong>{history.data.as_of || "--"}</strong>
                  </div>
                </div>
                <MarketIndexChart
                  name={history.data.name}
                  points={history.data.points}
                  seriesLabel="行业板块"
                />
                {historyCondition?.message ? <p className="market-data-note">{historyCondition.message}</p> : null}
              </>
            ) : null}
          </div>
        </div>
      ) : null}

      <p className="market-sector-boundary">
        行业板块行情只用于市场观察，不构成板块推荐，不改变主评分或主风险。
      </p>
    </section>
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
  const dataCondition = state.data
    ? getDataCondition({
        stale: state.data.stale,
        fallbackUsed: state.data.fallback_used,
        dataQualityGrade: state.data.data_quality_grade
      })
    : null;
  return (
    <section id="market-index" className="content-band market-index-panel" aria-labelledby="market-index-title">
      <div className="market-index-toolbar">
        <div>
          <p className="eyebrow">指数走势</p>
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
        <StatePanel kind="loading" title="正在读取指数日线" description="正在加载所选指数的历史走势。" />
      ) : null}
      {state.error ? (
        <StatePanel kind="error" title="指数日线暂不可用" description="暂时无法读取该指数的历史走势，请稍后刷新页面。" />
      ) : null}
      {state.data && state.data.points.length ? (
        <div className="market-index-workspace">
          <div className="market-index-main">
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
                <span>数据日期</span>
                <strong>{state.data.as_of || "--"}</strong>
              </div>
            </div>
            <MarketIndexChart name={state.data.name} points={state.data.points} />
          </div>
          {dataCondition?.message ? <p className="market-data-note">{dataCondition.message}</p> : null}
        </div>
      ) : null}
    </section>
  );
}

function formatDateTime(value?: string | null) {
  if (!value) return "--";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(parsed);
}
