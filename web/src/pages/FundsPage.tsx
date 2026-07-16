import { CircleAlert, Database, SearchCheck } from "lucide-react";
import { useMemo, useState } from "react";

import type { FundDetailItem, FundsData } from "../api/types";
import { DataTable } from "../components/DataTable";
import { EvidenceDrawer } from "../components/EvidenceDrawer";
import { FilterBar } from "../components/FilterBar";
import { Metric } from "../components/Metric";
import { PageHeader } from "../components/PageHeader";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";

function formatReturn(value?: number | null) {
  if (value == null) return "--";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function FundsPage() {
  const { loading, resource, error } = useApiResource<FundsData>("/api/funds");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<FundDetailItem | null>(null);

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
    <div className="page-stack">
      <PageHeader
        eyebrow="Configured watchlist"
        title="自选研究"
        description="仅展示 configs/watchlist.yaml 中的基金与 ETF，不代表全市场筛选或推荐。"
        actions={<StatusBadge tone="info">自选池 {funds.length}</StatusBadge>}
      />

      <section className="metric-grid" aria-label="自选研究指标">
        <Metric label="自选详情" value={details.detail_count ?? funds.length} detail={`as_of ${details.as_of || "--"}`} />
        <Metric label="平均覆盖" value={coverage == null ? "--" : `${(coverage * 100).toFixed(0)}%`} detail={`缺失 ${details.missing_count ?? 0}`} />
        <Metric label="质量警告" value={details.warning_count ?? 0} detail="缺字段保留 warning" />
        <Metric label="候选信号" value={signalSummary.eligible_count ?? 0} detail={`排除 ${signalSummary.excluded_count ?? 0} · 展示 ${signalSummary.display_only_count ?? 0}`} />
      </section>

      <section className="content-band" aria-labelledby="watchlist-table-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Watchlist records</p>
            <h2 id="watchlist-table-title">配置中的观察基金</h2>
          </div>
          <SearchCheck size={19} aria-hidden />
        </div>
        <FilterBar searchLabel="搜索自选基金" searchValue={query} onSearchChange={setQuery} />
        {filtered.length ? (
          <DataTable label="自选基金数据表" minWidth={920}>
            <thead><tr><th>代码</th><th>名称</th><th>主题</th><th>净值</th><th>1 月</th><th>3 月</th><th>覆盖</th><th>来源</th><th aria-label="操作" /></tr></thead>
            <tbody>
              {filtered.map((fund) => {
                const oneMonth = fund.return_windows?.["1m"]?.total_return;
                const threeMonth = fund.return_windows?.["3m"]?.total_return;
                return (
                  <tr key={fund.code}>
                    <td><strong>{fund.code || "--"}</strong></td>
                    <td>{fund.name || "名称缺失"}</td>
                    <td>{fund.primary_theme && fund.primary_theme !== "unknown" ? fund.primary_theme : "未分类"}</td>
                    <td>{fund.nav == null ? "--" : fund.nav.toFixed(4)}</td>
                    <td className={Number(oneMonth) >= 0 ? "number-positive" : "number-negative"}>{formatReturn(oneMonth)}</td>
                    <td className={Number(threeMonth) >= 0 ? "number-positive" : "number-negative"}>{formatReturn(threeMonth)}</td>
                    <td><StatusBadge tone={fund.data_coverage?.status === "complete" ? "success" : "warning"}>{fund.data_coverage?.status || fund.data_quality_grade || "unknown"}</StatusBadge></td>
                    <td>{fund.source || "--"}</td>
                    <td><button className="table-action" type="button" aria-label={`查看${fund.code || "基金"}详情`} onClick={() => setSelected(fund)}>查看</button></td>
                  </tr>
                );
              })}
            </tbody>
          </DataTable>
        ) : <StatePanel kind="empty" title="没有匹配的自选基金" description="调整代码或名称搜索条件。" />}
      </section>

      <div className="notice notice--info">
        <Database size={18} aria-hidden />
        <div><strong>数据来自 watchlist enrichment</strong><p>缺少基金经理、评级、规模或 NAV history 时保留为空，不会转成正向信号。</p></div>
      </div>

      <EvidenceDrawer open={selected !== null} title={`${selected?.code || "--"} 基金详情`} onClose={() => setSelected(null)}>
        {selected ? (
          <div className="drawer-stack">
            <div><h3>{selected.name || "名称缺失"}</h3><p>{selected.fund_type || "类型未知"} · {selected.primary_theme || "主题未知"}</p></div>
            <dl className="detail-list">
              <div><dt>source / as_of</dt><dd>{selected.source || "--"} · {selected.as_of || "--"}</dd></div>
              <div><dt>数据质量</dt><dd>{selected.data_quality_grade || "unknown"}</dd></div>
              <div><dt>覆盖比例</dt><dd>{selected.data_coverage?.coverage_ratio == null ? "--" : `${(selected.data_coverage.coverage_ratio * 100).toFixed(0)}%`}</dd></div>
              <div><dt>缺失字段</dt><dd>{selected.missing_fields?.length ? selected.missing_fields.join(" · ") : "无"}</dd></div>
            </dl>
            {selected.missing_fields?.length ? (
              <div className="notice"><CircleAlert size={18} aria-hidden /><div><strong>缺失字段不会形成正向信号</strong><p>需补充可靠来源并通过回归验证后，才可能进入实验候选层。</p></div></div>
            ) : null}
          </div>
        ) : null}
      </EvidenceDrawer>
    </div>
  );
}
