import {
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Database,
  Search,
  SearchCheck,
  SlidersHorizontal
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { searchFunds } from "../api/client";
import type {
  FundDetailItem,
  FundSearchItem,
  FundSearchParams,
  FundSearchResponse,
  FundsData
} from "../api/types";
import { DataTable } from "../components/DataTable";
import { FilterBar } from "../components/FilterBar";
import { Metric } from "../components/Metric";
import { PageHeader } from "../components/PageHeader";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge, type StatusTone } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";

type FundView = "market" | "watchlist";
type MarketState = {
  loading: boolean;
  data: FundSearchResponse | null;
  error: string | null;
};

const DEFAULT_SEARCH: FundSearchParams = {
  q: "",
  sort: "code",
  direction: "asc",
  page: 1,
  pageSize: 25
};

function formatReturn(value?: number | null) {
  if (value == null) return "--";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatNumber(value?: number | null, digits = 2) {
  if (value == null) return "--";
  return value.toLocaleString("zh-CN", { maximumFractionDigits: digits });
}

function qualityTone(quality?: string | null): StatusTone {
  if (quality === "normal" || quality === "complete") return "success";
  if (quality === "degraded" || quality === "critical") return "critical";
  if (quality === "warning" || quality === "partial") return "warning";
  return "neutral";
}

function returnClass(value?: number | null) {
  if (value == null || value === 0) return "";
  return value > 0 ? "number-positive" : "number-negative";
}

export function FundsPage() {
  const [urlSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const searchKey = urlSearchParams.toString();
  const watchlist = useApiResource<FundsData>("/api/funds");
  const [view, setView] = useState<FundView>("market");
  const [search, setSearch] = useState<FundSearchParams>(() => readSearchParams(urlSearchParams));
  const [market, setMarket] = useState<MarketState>({ loading: true, data: null, error: null });

  useEffect(() => {
    setView("market");
    setSearch(readSearchParams(urlSearchParams));
  }, [searchKey, urlSearchParams]);

  useEffect(() => {
    const controller = new AbortController();
    setMarket((current) => ({ loading: true, data: current.data, error: null }));
    searchFunds(search, controller.signal)
      .then((data) => setMarket({ loading: false, data, error: null }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setMarket({
          loading: false,
          data: null,
          error: error instanceof Error ? error.message : "全市场基金数据读取失败。"
        });
      });
    return () => controller.abort();
  }, [search]);

  const selectFund = (code: string) => {
    const returnTo = `${location.pathname}${location.search}`;
    navigate(`/funds/${code}?return_to=${encodeURIComponent(returnTo)}`);
  };

  const setSearchField = <K extends keyof FundSearchParams>(key: K, value: FundSearchParams[K]) => {
    setSearch((current) => {
      const next = { ...current, [key]: value, page: key === "page" ? Number(value) : 1 };
      navigate({ pathname: "/funds", search: toSearchString(next) }, { replace: true });
      return next;
    });
  };

  const marketData = market.data;
  const watchlistDetails = watchlist.resource?.data.details || {};
  const watchlistFunds = watchlistDetails.fund_details || watchlistDetails.funds || [];

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Fund terminal"
        title="基金终端"
        description="浏览全市场结构化数据，并与配置中的自选池分开核验。结果仅用于研究观察，不构成推荐。"
        actions={
          <StatusBadge tone={qualityTone(marketData?.data_quality_grade)}>
            {marketData?.source || "数据待加载"} · {marketData?.as_of || "--"}
          </StatusBadge>
        }
      />

      <div className="view-tabs" role="tablist" aria-label="基金数据范围">
        <button
          type="button"
          role="tab"
          aria-label="全市场"
          aria-selected={view === "market"}
          className={view === "market" ? "view-tab view-tab--active" : "view-tab"}
          onClick={() => setView("market")}
        >
          全市场
          <span>{marketData?.total.toLocaleString("zh-CN") || "--"}</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-label="我的自选"
          aria-selected={view === "watchlist"}
          className={view === "watchlist" ? "view-tab view-tab--active" : "view-tab"}
          onClick={() => setView("watchlist")}
        >
          我的自选
          <span>{watchlistFunds.length}</span>
        </button>
      </div>

      {view === "market" ? (
        <MarketExplorer
          state={market}
          search={search}
          onSearchChange={setSearchField}
          onSelect={selectFund}
        />
      ) : (
        <WatchlistView
          loading={watchlist.loading}
          resource={watchlist.resource}
          error={watchlist.error}
          onSelect={selectFund}
        />
      )}

    </div>
  );
}

function readSearchParams(params: URLSearchParams): FundSearchParams {
  const page = Number(params.get("page"));
  const pageSize = Number(params.get("page_size"));
  const exchangeTraded = params.get("exchange_traded");
  return {
    ...DEFAULT_SEARCH,
    q: params.get("q")?.trim() || "",
    fundType: params.get("fund_type") || undefined,
    theme: params.get("theme") || undefined,
    quality: (params.get("quality") || undefined) as FundSearchParams["quality"],
    sort: (params.get("sort") || DEFAULT_SEARCH.sort) as FundSearchParams["sort"],
    direction: (params.get("direction") || DEFAULT_SEARCH.direction) as FundSearchParams["direction"],
    exchangeTraded: exchangeTraded === "true" ? true : undefined,
    page: Number.isFinite(page) && page > 0 ? page : DEFAULT_SEARCH.page,
    pageSize: Number.isFinite(pageSize) && pageSize > 0 ? pageSize : DEFAULT_SEARCH.pageSize
  };
}

function toSearchString(search: FundSearchParams): string {
  const params = new URLSearchParams();
  if (search.q) params.set("q", search.q);
  if (search.fundType) params.set("fund_type", search.fundType);
  if (search.theme) params.set("theme", search.theme);
  if (search.quality) params.set("quality", search.quality);
  if (search.sort && search.sort !== DEFAULT_SEARCH.sort) params.set("sort", search.sort);
  if (search.direction && search.direction !== DEFAULT_SEARCH.direction) params.set("direction", search.direction);
  if (search.exchangeTraded) params.set("exchange_traded", "true");
  if (search.page && search.page !== DEFAULT_SEARCH.page) params.set("page", String(search.page));
  if (search.pageSize && search.pageSize !== DEFAULT_SEARCH.pageSize) params.set("page_size", String(search.pageSize));
  const value = params.toString();
  return value ? `?${value}` : "";
}

function MarketExplorer({
  state,
  search,
  onSearchChange,
  onSelect
}: {
  state: MarketState;
  search: FundSearchParams;
  onSearchChange: <K extends keyof FundSearchParams>(key: K, value: FundSearchParams[K]) => void;
  onSelect: (code: string) => void;
}) {
  const data = state.data;
  const fundTypes = Object.keys(data?.facets.fund_types || {});
  const themes = Object.keys(data?.facets.themes || {});

  if (state.loading && !data) {
    return <StatePanel kind="loading" title="正在建立全市场索引" description="仅向浏览器传输当前页，不加载全部基金记录。" />;
  }
  if (state.error) {
    return <StatePanel kind="error" title="全市场数据读取失败" description={state.error} />;
  }
  if (!data || data.availability === "missing") {
    return <StatePanel kind="empty" title="尚无全市场基金数据" description="运行启用 Market Intelligence 的 daily ops 后再查看。" />;
  }

  const etfCount = data.facets.exchange_traded.true || 0;
  return (
    <>
      <section className="metric-grid" aria-label="全市场基金指标">
        <Metric label="匹配基金" value={data.total.toLocaleString("zh-CN")} detail={`每页 ${data.page_size} 条`} />
        <Metric label="ETF" value={etfCount.toLocaleString("zh-CN")} detail="当前筛选范围" />
        <Metric label="数据日期" value={data.as_of || "--"} detail={data.source || "unknown"} />
        <Metric label="数据质量" value={data.data_quality_grade} detail={data.index_stale ? "索引使用上次成功数据" : "索引已同步"} />
      </section>

      {(data.index_stale || data.warnings.length > 0) && (
        <div className="notice">
          <CircleAlert size={18} aria-hidden />
          <div>
            <strong>当前数据存在质量提示</strong>
            <p>{data.warnings.join(" · ") || "索引使用上次成功数据，请核对 daily 产物。"}</p>
          </div>
        </div>
      )}

      <section className="content-band" aria-labelledby="market-funds-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Server-side search</p>
            <h2 id="market-funds-title">全市场基金与 ETF</h2>
          </div>
          <SlidersHorizontal size={19} aria-hidden />
        </div>

        <div className="fund-filter-grid">
          <label className="search-control fund-search-control">
            <Search size={17} aria-hidden />
            <span className="sr-only">搜索全市场基金</span>
            <input
              type="search"
              aria-label="搜索全市场基金"
              placeholder="输入代码或基金名称"
              value={search.q || ""}
              onChange={(event) => onSearchChange("q", event.target.value)}
            />
          </label>
          <FilterSelect
            label="基金类型"
            value={search.fundType || ""}
            options={fundTypes}
            allLabel="全部类型"
            onChange={(value) => onSearchChange("fundType", value || undefined)}
          />
          <FilterSelect
            label="主题"
            value={search.theme || ""}
            options={themes}
            allLabel="全部主题"
            onChange={(value) => onSearchChange("theme", value || undefined)}
          />
          <FilterSelect
            label="数据质量"
            value={search.quality || ""}
            options={["normal", "warning", "degraded", "unknown"]}
            allLabel="全部质量"
            onChange={(value) => onSearchChange("quality", (value || undefined) as FundSearchParams["quality"])}
          />
          <FilterSelect
            label="排序"
            value={search.sort || "code"}
            options={["code", "name", "return_1m", "return_3m", "return_6m", "return_1y"]}
            labels={{
              code: "代码",
              name: "名称",
              return_1m: "1 月收益",
              return_3m: "3 月收益",
              return_6m: "6 月收益",
              return_1y: "1 年收益"
            }}
            onChange={(value) => onSearchChange("sort", value as FundSearchParams["sort"])}
          />
          <label className="toggle-control">
            <input
              type="checkbox"
              checked={search.exchangeTraded === true}
              onChange={(event) => onSearchChange("exchangeTraded", event.target.checked ? true : undefined)}
            />
            <span>仅 ETF</span>
          </label>
        </div>

        {state.loading ? <p className="inline-loading" role="status">正在更新结果…</p> : null}
        {data.items.length ? (
          <MarketFundTable items={data.items} onSelect={onSelect} />
        ) : (
          <StatePanel kind="empty" title="没有匹配的基金" description="调整代码、名称、类型、主题或质量条件。" />
        )}

        <div className="pagination-bar" aria-label="基金搜索分页">
          <p>
            第 <strong>{data.page}</strong> / {data.total_pages || 1} 页 · 共 {data.total.toLocaleString("zh-CN")} 条
          </p>
          <div>
            <button
              className="icon-button"
              type="button"
              aria-label="上一页"
              title="上一页"
              disabled={data.page <= 1 || state.loading}
              onClick={() => onSearchChange("page", Math.max(1, data.page - 1))}
            >
              <ChevronLeft size={18} aria-hidden />
            </button>
            <button
              className="icon-button"
              type="button"
              aria-label="下一页"
              title="下一页"
              disabled={data.page >= data.total_pages || state.loading}
              onClick={() => onSearchChange("page", data.page + 1)}
            >
              <ChevronRight size={18} aria-hidden />
            </button>
          </div>
        </div>
      </section>

      <div className="notice notice--info">
        <Database size={18} aria-hidden />
        <div>
          <strong>全市场搜索来自结构化 Market Intelligence 产物</strong>
          <p>搜索结果不是推荐榜单；来源、日期、stale 和缺失字段必须与研究结论一起核对。</p>
        </div>
      </div>
    </>
  );
}

function MarketFundTable({ items, onSelect }: { items: FundSearchItem[]; onSelect: (code: string) => void }) {
  return (
    <DataTable label="全市场基金数据表" minWidth={1120}>
      <thead>
        <tr>
          <th>代码</th><th>名称</th><th>类型</th><th>主题</th><th>净值</th><th>1 月</th><th>3 月</th><th>质量</th><th>来源 / 日期</th><th aria-label="操作" />
        </tr>
      </thead>
      <tbody>
        {items.map((fund) => (
          <tr key={fund.code}>
            <td><strong>{fund.code}</strong></td>
            <td className="fund-name-cell">{fund.name || "名称缺失"}</td>
            <td>{fund.fund_type || "unknown"}</td>
            <td>{fund.primary_theme && fund.primary_theme !== "unknown" ? fund.primary_theme : "未分类"}</td>
            <td>{formatNumber(fund.nav, 4)}</td>
            <td className={returnClass(fund.returns["1m"])}>{formatReturn(fund.returns["1m"])}</td>
            <td className={returnClass(fund.returns["3m"])}>{formatReturn(fund.returns["3m"])}</td>
            <td><StatusBadge tone={qualityTone(fund.data_quality_grade)}>{fund.stale ? "stale" : fund.data_quality_grade}</StatusBadge></td>
            <td><span className="source-cell">{fund.source}<small>{fund.as_of || "--"}</small></span></td>
            <td><button className="table-action" type="button" aria-label={`查看${fund.code}详情`} onClick={() => onSelect(fund.code)}>查看</button></td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}

function WatchlistView({
  loading,
  resource,
  error,
  onSelect
}: {
  loading: boolean;
  resource: ReturnType<typeof useApiResource<FundsData>>["resource"];
  error: string | null;
  onSelect: (code: string) => void;
}) {
  const [query, setQuery] = useState("");
  const details = resource?.data.details || {};
  const funds = details.fund_details || details.funds || [];
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return funds;
    return funds.filter((fund) => `${fund.code || ""} ${fund.name || ""}`.toLowerCase().includes(normalized));
  }, [funds, query]);

  if (loading) return <StatePanel kind="loading" title="正在读取自选研究" description="加载 watchlist 对应的基金详情和候选信号摘要。" />;
  if (error) return <StatePanel kind="error" title="自选研究读取失败" description={error} />;
  if (!resource || resource.availability === "missing") {
    return <StatePanel kind="empty" title="尚无自选基金详情" description="运行 daily ops 生成 watchlist_fund_details.json 后再查看。" />;
  }

  const signalSummary = resource.data.signal_candidates?.summary || {};
  const coverage = details.coverage_summary?.average_coverage_ratio;
  return (
    <>
      <section className="metric-grid" aria-label="自选研究指标">
        <Metric label="自选详情" value={details.detail_count ?? funds.length} detail={`as_of ${details.as_of || "--"}`} />
        <Metric label="平均覆盖" value={coverage == null ? "--" : `${(coverage * 100).toFixed(0)}%`} detail={`缺失 ${details.missing_count ?? 0}`} />
        <Metric label="质量警告" value={details.warning_count ?? 0} detail="缺字段保留 warning" />
        <Metric label="候选信号" value={signalSummary.eligible_count ?? 0} detail={`排除 ${signalSummary.excluded_count ?? 0} · 展示 ${signalSummary.display_only_count ?? 0}`} />
      </section>

      <section className="content-band" aria-labelledby="watchlist-table-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Configured watchlist</p>
            <h2 id="watchlist-table-title">配置中的观察基金</h2>
          </div>
          <StatusBadge tone="info">仅来自 configs/watchlist.yaml</StatusBadge>
        </div>
        <FilterBar searchLabel="搜索自选基金" searchValue={query} onSearchChange={setQuery} />
        {filtered.length ? (
          <DataTable label="自选基金数据表" minWidth={920}>
            <thead><tr><th>代码</th><th>名称</th><th>主题</th><th>净值</th><th>1 月</th><th>3 月</th><th>覆盖</th><th>来源</th><th aria-label="操作" /></tr></thead>
            <tbody>
              {filtered.map((fund) => (
                <WatchlistRow key={fund.code} fund={fund} onSelect={onSelect} />
              ))}
            </tbody>
          </DataTable>
        ) : <StatePanel kind="empty" title="没有匹配的自选基金" description="调整代码或名称搜索条件。" />}
      </section>

      <div className="notice notice--info">
        <SearchCheck size={18} aria-hidden />
        <div><strong>自选池与全市场搜索是两个范围</strong><p>自选池只反映本地配置，不代表系统推荐；缺失字段不会转成正向信号。</p></div>
      </div>
    </>
  );
}

function WatchlistRow({ fund, onSelect }: { fund: FundDetailItem; onSelect: (code: string) => void }) {
  const oneMonth = fund.return_windows?.["1m"]?.total_return;
  const threeMonth = fund.return_windows?.["3m"]?.total_return;
  return (
    <tr>
      <td><strong>{fund.code || "--"}</strong></td>
      <td className="fund-name-cell">{fund.name || "名称缺失"}</td>
      <td>{fund.primary_theme && fund.primary_theme !== "unknown" ? fund.primary_theme : "未分类"}</td>
      <td>{fund.nav == null ? "--" : fund.nav.toFixed(4)}</td>
      <td className={returnClass(oneMonth)}>{formatReturn(oneMonth)}</td>
      <td className={returnClass(threeMonth)}>{formatReturn(threeMonth)}</td>
      <td><StatusBadge tone={qualityTone(fund.data_coverage?.status || fund.data_quality_grade)}>{fund.data_coverage?.status || fund.data_quality_grade || "unknown"}</StatusBadge></td>
      <td>{fund.source || "--"}</td>
      <td><button className="table-action" type="button" aria-label={`查看${fund.code || "基金"}详情`} onClick={() => fund.code && onSelect(fund.code)}>查看</button></td>
    </tr>
  );
}

function FilterSelect({
  label,
  value,
  options,
  allLabel,
  labels = {},
  onChange
}: {
  label: string;
  value: string;
  options: string[];
  allLabel?: string;
  labels?: Record<string, string>;
  onChange: (value: string) => void;
}) {
  return (
    <label className="compact-select">
      <span>{label}</span>
      <select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)}>
        {allLabel ? <option value="">{allLabel}</option> : null}
        {options.map((option) => <option key={option} value={option}>{labels[option] || option}</option>)}
      </select>
    </label>
  );
}
