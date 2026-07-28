import { ArrowDownRight, ArrowUpRight, History, RefreshCw, Search, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  getProductMarketIndexHistory,
  getProductMarketSectorHistory,
  searchProductMarketSectors
} from "../api/client";
import type {
  MarketIndexWindow,
  ProductDataStatus,
  ProductMarketHistoryResponse,
  ProductMarketData,
  ProductMarketSectorItem,
  ProductMarketSectorSearchResponse,
  ProductThemeSummary
} from "../api/types";
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
  data: ProductMarketHistoryResponse | null;
  error: string | null;
};

type SectorCatalogState = {
  loading: boolean;
  data: ProductMarketSectorSearchResponse | null;
  error: string | null;
};

type SectorHistoryState = {
  loading: boolean;
  data: ProductMarketHistoryResponse | null;
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

function dataStatusTone(status?: ProductDataStatus | null): StatusTone {
  if (status?.state === "updated") return "success";
  if (status?.state === "attention") return "warning";
  if (status?.state === "limited" || status?.state === "unavailable") return "critical";
  return "neutral";
}

function themeReadiness(theme: ProductThemeSummary): { label: string; tone: StatusTone } {
  if (theme.sample_size === null || theme.sample_size === undefined) {
    return { label: "待补充", tone: "neutral" };
  }
  return { label: theme.data_status.label, tone: dataStatusTone(theme.data_status) };
}

export function MarketPage() {
  const { loading, resource, error, refresh, refreshVersion } = useApiResource<ProductMarketData>("/api/product/market");
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
  const [selectedSector, setSelectedSector] = useState<ProductMarketSectorItem | null>(null);
  const [sectorWindow, setSectorWindow] = useState<MarketIndexWindow>("6m");
  const [sectorHistory, setSectorHistory] = useState<SectorHistoryState>({
    loading: false,
    data: null,
    error: null
  });

  const topThemes = useMemo(() => resource?.data.themes || [], [resource]);

  useEffect(() => {
    const controller = new AbortController();
    setIndexHistory({ loading: true, data: null, error: null });
    getProductMarketIndexHistory(selectedIndex, indexWindow, controller.signal)
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
    searchProductMarketSectors(
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
    getProductMarketSectorHistory(
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
          eyebrow="市场行情"
          title="行情总览"
          description="主要指数可独立按需读取；主题与趋势仍依赖每日 Market Intelligence 产物。"
          actions={<StatusBadge tone="neutral">仅指数可浏览</StatusBadge>}
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
          description="指数浏览仍可使用；完成一次日常更新后，主题与趋势信息会显示在这里。"
        />
      </div>
    );
  }

  const market = resource.data;
  const trend = market.trend;
  const marketCondition = market.data_status;
  const persistent = trend.persistent || [];
  const newThemes = trend.new || [];
  const rising = trend.rising || [];

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
          <b>{market.as_of || "--"}</b>
        </div>
        <div className="market-pulse__fact">
          <span>覆盖范围</span>
          <strong>全市场基金与 ETF</strong>
        </div>
        <div className="market-pulse__fact">
          <span>资料状态</span>
          <StatusBadge tone={dataStatusTone(marketCondition)}>{marketCondition.label}</StatusBadge>
        </div>
      </section>

      <section className="metric-grid market-coverage-rail" aria-label="市场覆盖指标">
        <Metric label="基金覆盖" value={number.format(market.coverage.fund_count || 0)} detail="全市场基础索引" />
        <Metric label="ETF 覆盖" value={number.format(market.coverage.etf_count || 0)} detail="可进入基金终端搜索" />
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
          <span className="section-meta">截至 {market.as_of || "--"}</span>
        </div>
        <div className="table-wrap">
          <table className="data-table theme-window-table">
            <thead>
              <tr>
                <th>主题</th>
                <th>1 周</th>
                <th>1 月</th>
                <th>3 月</th>
                <th>正收益占比</th>
                <th>样本</th>
                <th>解读提示</th>
              </tr>
            </thead>
            <tbody>
              {topThemes.slice(0, 12).map((theme) => {
                const readiness = themeReadiness(theme);
                return (
                <tr key={theme.name}>
                  <td>
                    {theme.name ? (
                      <button
                        className="theme-table-select"
                        type="button"
                        aria-label={`搜索${theme.name}同名行业板块`}
                        title="查看同名行业板块"
                        onClick={() => searchMatchingSector(theme.name || "")}
                      >
                        {theme.name}
                      </button>
                    ) : (
                      <strong>未分类</strong>
                    )}
                  </td>
                  <td className={returnClass(theme.returns["1w"])}>{formatReturn(theme.returns["1w"])}</td>
                  <td className={returnClass(theme.returns["1m"])}>{formatReturn(theme.returns["1m"])}</td>
                  <td className={returnClass(theme.returns["3m"])}>{formatReturn(theme.returns["3m"])}</td>
                  <td>{theme.positive_ratio_1m == null ? "--" : `${(theme.positive_ratio_1m * 100).toFixed(1)}%`}</td>
                  <td>{number.format(theme.sample_size || 0)}</td>
                  <td><StatusBadge tone={readiness.tone}>{readiness.label}</StatusBadge></td>
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
              <button className="movement-item movement-item--interactive" type="button" key={`rise-${item.name}`} onClick={() => searchMatchingSector(item.name || "")}>
                <ArrowUpRight className="number-positive" size={18} aria-hidden />
                <strong>{item.name || "未分类"}</strong>
                <span>排名 +{item.rank_change ?? 0}</span>
              </button>
            ))}
            {newThemes.slice(0, 4).map((item) => (
              <button className="movement-item movement-item--interactive" type="button" key={`new-${item.name}`} onClick={() => searchMatchingSector(item.name || "")}>
                <Sparkles className="number-positive" size={18} aria-hidden />
                <strong>{item.name || "未分类"}</strong>
                <span>新进入观察</span>
              </button>
            ))}
            {(trend.falling || []).slice(0, 2).map((item) => (
              <button className="movement-item movement-item--interactive" type="button" key={`fall-${item.name}`} onClick={() => searchMatchingSector(item.name || "")}>
                <ArrowDownRight className="number-negative" size={18} aria-hidden />
                <strong>{item.name || "未分类"}</strong>
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
  selectedSector: ProductMarketSectorItem | null;
  window: MarketIndexWindow;
  onQueryChange: (query: string) => void;
  onSearch: () => void;
  onSectorChange: (sector: ProductMarketSectorItem) => void;
  onWindowChange: (window: MarketIndexWindow) => void;
}) {
  const latest = history.data?.points.at(-1);
  const catalogStatus = catalog.data?.data_status;
  const historyStatus = history.data?.data_status;
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
      {catalog.data?.availability === "missing" ? (
        <StatePanel
          kind="empty"
          title="行业板块暂不可用"
          description={catalogStatus?.description || "当前没有可展示的行业板块数据。"}
        />
      ) : null}
      {catalog.data?.availability === "available" && !catalog.data.items.length ? (
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
            {catalogStatus && catalogStatus.state !== "updated" ? <p className="market-data-note">{catalogStatus.description}</p> : null}
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
            {history.data?.availability === "missing" ? (
              <StatePanel
                kind="empty"
                title="板块日线暂不可用"
                description={historyStatus?.description || "当前没有可展示的板块历史数据。"}
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
                    <strong>{history.data.data_date || "--"}</strong>
                  </div>
                </div>
                <MarketIndexChart
                  name={history.data.name}
                  points={history.data.points}
                  seriesLabel="行业板块"
                />
                {historyStatus && historyStatus.state !== "updated" ? <p className="market-data-note">{historyStatus.description}</p> : null}
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
  const dataStatus = state.data?.data_status;
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
      {state.data?.availability === "missing" ? (
        <StatePanel
          kind="empty"
          title="指数日线暂不可用"
          description={dataStatus?.description || "当前没有可展示的指数历史数据。"}
        />
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
                <strong>{state.data.data_date || "--"}</strong>
              </div>
            </div>
            <MarketIndexChart name={state.data.name} points={state.data.points} />
          </div>
        {dataStatus && dataStatus.state !== "updated" ? <p className="market-data-note">{dataStatus.description}</p> : null}
        </div>
      ) : null}
    </section>
  );
}
