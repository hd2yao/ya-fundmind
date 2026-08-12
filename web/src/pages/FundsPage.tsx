import {
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Search,
  SearchCheck,
  SlidersHorizontal
} from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { searchFunds } from "../api/client";
import type {
  FundSearchParams,
  ProductDataStatus,
  ProductFundSearchResponse,
  ProductFundSummary
} from "../api/types";
import { DataTable } from "../components/DataTable";
import { FilterBar } from "../components/FilterBar";
import { Metric } from "../components/Metric";
import { PageHeader } from "../components/PageHeader";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge, type StatusTone } from "../components/StatusBadge";
type MarketState = {
  loading: boolean;
  data: ProductFundSearchResponse | null;
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

function dataStatusTone(status?: ProductDataStatus | null): StatusTone {
  if (status?.state === "updated") return "success";
  if (status?.state === "attention") return "warning";
  if (status?.state === "limited" || status?.state === "unavailable") return "critical";
  return "neutral";
}

function returnClass(value?: number | null) {
  if (value == null || value === 0) return "";
  return value > 0 ? "number-positive" : "number-negative";
}

function purchaseStatusTone(status?: string | null): StatusTone {
  if (!status) return "neutral";
  if (status.includes("暂停") || status.includes("限制") || status.includes("封闭")) return "warning";
  return "success";
}

export function FundsPage() {
  const [urlSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const searchKey = urlSearchParams.toString();
  const [search, setSearch] = useState<FundSearchParams>(() => readSearchParams(urlSearchParams));
  const [market, setMarket] = useState<MarketState>({ loading: true, data: null, error: null });

  useEffect(() => {
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

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="基金资料"
        title="基金终端"
        description="浏览全市场结构化数据并进入基金详情。结果仅用于研究观察，不构成推荐。"
      />
      <MarketExplorer
        state={market}
        search={search}
        onSearchChange={setSearchField}
        onSelect={selectFund}
      />
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
    purchaseStatus: params.get("purchase_status") || undefined,
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
  if (search.purchaseStatus) params.set("purchase_status", search.purchaseStatus);
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
  const purchaseStatuses = Object.keys(data?.facets.purchase_statuses || {});

  if (state.loading && !data) {
    return <StatePanel kind="loading" title="正在建立全市场索引" description="仅向浏览器传输当前页，不加载全部基金记录。" />;
  }
  if (state.error) {
    return <StatePanel kind="error" title="全市场数据读取失败" description={state.error} />;
  }
  if (!data || data.availability === "missing") {
    return <StatePanel kind="empty" title="尚无全市场基金数据" description="完成每日数据更新后再查看。" />;
  }

  const etfCount = data.facets.exchange_traded.true || 0;
  return (
    <>
      <section className="metric-grid" aria-label="全市场基金指标">
        <Metric label="匹配基金" value={data.total.toLocaleString("zh-CN")} detail={`每页 ${data.page_size} 条`} />
        <Metric label="ETF" value={etfCount.toLocaleString("zh-CN")} detail="当前筛选范围" />
        <Metric label="数据日期" value={data.data_date || "--"} detail="全市场结构化索引" />
        <Metric label="资料状态" value={data.data_status.label} detail={data.data_status.description} />
      </section>

      {data.data_status.state !== "updated" && (
        <div className="notice">
          <CircleAlert size={18} aria-hidden />
          <div>
            <strong>{data.data_status.label}</strong>
            <p>{data.data_status.description}</p>
          </div>
        </div>
      )}

      <section className="content-band" aria-labelledby="market-funds-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">基金检索</p>
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
            allLabel="全部状态"
            labels={{ normal: "数据已更新", warning: "请留意数据日期", degraded: "资料暂不完整", unknown: "暂无法判断" }}
            onChange={(value) => onSearchChange("quality", (value || undefined) as FundSearchParams["quality"])}
          />
          <FilterSelect
            label="申购状态"
            value={search.purchaseStatus || ""}
            options={purchaseStatuses}
            allLabel="全部申购状态"
            onChange={(value) => onSearchChange("purchaseStatus", value || undefined)}
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
          <StatePanel kind="empty" title="没有匹配的基金" description="调整代码、名称、类型、主题、申购状态或质量条件。" />
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
        <SearchCheck size={18} aria-hidden />
        <div>
          <strong>全市场搜索不是推荐榜单</strong>
          <p>请结合基金资料、数据日期和个人研究目标进行人工核对。</p>
        </div>
      </div>
    </>
  );
}

function MarketFundTable({ items, onSelect }: { items: ProductFundSummary[]; onSelect: (code: string) => void }) {
  return (
    <DataTable label="全市场基金数据表" minWidth={1240}>
      <thead>
        <tr>
          <th>代码</th><th>名称</th><th>类型</th><th>主题</th><th>申购状态</th><th>净值</th><th>1 月</th><th>3 月</th><th>资料状态</th><th aria-label="操作" />
        </tr>
      </thead>
      <tbody>
        {items.map((fund, index) => {
          const code = fund.code || "";
          return (
          <tr key={code || `${fund.name || "fund"}-${index}`}>
            <td><strong>{code || "--"}</strong></td>
            <td className="fund-name-cell">{fund.name || "名称缺失"}</td>
            <td>{fund.fund_type || "类型待补充"}</td>
            <td>{fund.primary_theme || "未分类"}</td>
            <td><StatusBadge tone={purchaseStatusTone(fund.purchase_status)}>{fund.purchase_status || "待补充"}</StatusBadge></td>
            <td>{formatNumber(fund.nav, 4)}</td>
            <td className={returnClass(fund.returns["1m"])}>{formatReturn(fund.returns["1m"])}</td>
            <td className={returnClass(fund.returns["3m"])}>{formatReturn(fund.returns["3m"])}</td>
            <td><StatusBadge tone={dataStatusTone(fund.data_status)}>{fund.data_status.label}</StatusBadge></td>
            <td><button className="table-action" type="button" aria-label={`查看${code || "基金"}详情`} disabled={!code} onClick={() => code && onSelect(code)}>查看</button></td>
          </tr>
          );
        })}
      </tbody>
    </DataTable>
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
