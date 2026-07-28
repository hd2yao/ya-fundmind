import { CircleAlert, SearchCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { ProductDataStatus, ProductWatchlistData, ProductWatchlistFund } from "../api/types";
import { DataTable } from "../components/DataTable";
import { FilterBar } from "../components/FilterBar";
import { Metric } from "../components/Metric";
import { PageHeader } from "../components/PageHeader";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge, type StatusTone } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";

function formatReturn(value?: number | null) {
  if (value == null) return "--";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function returnClass(value?: number | null) {
  if (value == null || value === 0) return "";
  return value > 0 ? "number-positive" : "number-negative";
}

function dataStatusTone(status?: ProductDataStatus | null): StatusTone {
  if (status?.state === "updated") return "success";
  if (status?.state === "attention") return "warning";
  if (status?.state === "limited" || status?.state === "unavailable") return "critical";
  return "neutral";
}

export function WatchlistPage() {
  const { loading, resource, error } = useApiResource<ProductWatchlistData>("/api/product/watchlist");
  const [query, setQuery] = useState("");
  const navigate = useNavigate();
  const details = resource?.data;
  const funds = details?.funds || [];
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return funds;
    return funds.filter((fund) => `${fund.code || ""} ${fund.name || ""}`.toLowerCase().includes(normalized));
  }, [funds, query]);

  if (loading) return <StatePanel kind="loading" title="正在读取自选" description="加载当前配置中的观察基金资料。" />;
  if (error) return <StatePanel kind="error" title="自选资料读取失败" description={error} />;
  if (!resource || resource.availability === "missing") {
    return <StatePanel kind="empty" title="尚无自选资料" description="完成日常数据更新后，再查看配置中的观察基金。" />;
  }

  const coverage = details?.coverage_ratio;
  const selectFund = (code: string) => navigate(`/funds/${code}?return_to=${encodeURIComponent("/watchlist")}`);

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="配置观察"
        title="自选"
        description="展示当前配置中的观察基金，与全市场搜索和组合持仓分开。此页面只读，不构成推荐。"
        actions={<StatusBadge tone="info">只读观察</StatusBadge>}
      />

      <section className="metric-grid" aria-label="自选指标">
        <Metric label="观察基金" value={details?.detail_count ?? funds.length} detail={`数据日期 ${details?.as_of || "--"}`} />
        <Metric label="资料覆盖" value={coverage == null ? "--" : `${(coverage * 100).toFixed(0)}%`} detail="按已获取资料计算" />
        <Metric label="资料状态" value={details?.data_status.label || "--"} detail={details?.data_status.description || "--"} />
        <Metric label="可查看详情" value={funds.length} detail="点击基金进入资料页" />
      </section>

      <section className="content-band" aria-labelledby="watchlist-table-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">我的关注</p>
            <h2 id="watchlist-table-title">配置中的观察基金</h2>
          </div>
        </div>
        <FilterBar searchLabel="搜索自选基金" searchValue={query} onSearchChange={setQuery} />
        {filtered.length ? (
          <DataTable label="自选基金数据表" minWidth={820}>
            <thead><tr><th>代码</th><th>名称</th><th>主题</th><th>净值</th><th>1 月</th><th>3 月</th><th>资料状态</th><th aria-label="操作" /></tr></thead>
            <tbody>
              {filtered.map((fund) => <WatchlistRow key={fund.code} fund={fund} onSelect={selectFund} />)}
            </tbody>
          </DataTable>
        ) : <StatePanel kind="empty" title="没有匹配的自选基金" description="调整代码或名称搜索条件。" />}
      </section>

      <div className="notice notice--info">
        <SearchCheck size={18} aria-hidden />
        <div><strong>自选、全市场与组合是三个范围</strong><p>自选只反映当前观察设置；它不是推荐，也不等同于已配置持仓。缺失字段不会转成正向信号。</p></div>
      </div>

      {(details?.data_status.state !== "updated") ? (
        <div className="notice">
          <CircleAlert size={18} aria-hidden />
          <div><strong>{details?.data_status.label}</strong><p>{details?.data_status.description}</p></div>
        </div>
      ) : null}
    </div>
  );
}

function WatchlistRow({ fund, onSelect }: { fund: ProductWatchlistFund; onSelect: (code: string) => void }) {
  const oneMonth = fund.return_windows?.["1m"]?.total_return;
  const threeMonth = fund.return_windows?.["3m"]?.total_return;
  return (
    <tr>
      <td><strong>{fund.code || "--"}</strong></td>
      <td className="fund-name-cell">{fund.name || "名称缺失"}</td>
      <td>{fund.primary_theme || "未分类"}</td>
      <td>{fund.nav == null ? "--" : fund.nav.toFixed(4)}</td>
      <td className={returnClass(oneMonth)}>{formatReturn(oneMonth)}</td>
      <td className={returnClass(threeMonth)}>{formatReturn(threeMonth)}</td>
      <td><StatusBadge tone={dataStatusTone(fund.data_status)}>{fund.data_status.label}</StatusBadge></td>
      <td><button className="table-action" type="button" aria-label={`查看${fund.code || "基金"}详情`} onClick={() => fund.code && onSelect(fund.code)}>查看</button></td>
    </tr>
  );
}
