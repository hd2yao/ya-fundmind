import { CircleDollarSign, Layers3, TriangleAlert, WalletCards } from "lucide-react";
import type { CSSProperties } from "react";
import { Link } from "react-router-dom";

import type { ProductPortfolioData } from "../api/types";
import { DataTable } from "../components/DataTable";
import { Metric } from "../components/Metric";
import { PageHeader } from "../components/PageHeader";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";

const currency = new Intl.NumberFormat("zh-CN", { style: "currency", currency: "CNY", maximumFractionDigits: 2 });

type Exposure = { holding_count?: number; current_value?: number | null; weight?: number | null };

function isFundCode(value?: string | null): value is string {
  return Boolean(value && /^\d{6}$/.test(value));
}

function ExposureList({
  items,
  unavailable,
  emptyLabel
}: {
  items: Record<string, Exposure>;
  unavailable: boolean;
  emptyLabel: string;
}) {
  const entries = Object.entries(items);

  if (!entries.length) return <p className="empty-copy">{emptyLabel}</p>;

  return (
    <div className="exposure-list">
      {entries.map(([label, item]) => {
        const weight = typeof item.weight === "number" ? Math.max(0, Math.min(1, item.weight)) : null;
        const hasWeight = !unavailable && weight != null;
        const width = `${Math.round((weight || 0) * 100)}%`;
        return (
          <div className="exposure-item" key={label}>
            <div className="exposure-item__label"><strong>{label}</strong><span>{item.holding_count || 0} 只</span></div>
            <div className="exposure-item__weight">
              {hasWeight ? (
                <div
                  aria-label={`${label} 权重`}
                  aria-valuemax={100}
                  aria-valuemin={0}
                  aria-valuenow={Math.round((weight || 0) * 100)}
                  className="exposure-bar"
                  role="progressbar"
                  style={{ "--exposure-width": width } as CSSProperties}
                ><span /></div>
              ) : <span className="exposure-item__pending">权重待估值</span>}
              <strong>{hasWeight ? `${((weight || 0) * 100).toFixed(1)}%` : "--"}</strong>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function PortfolioPage() {
  const { loading, resource, error } = useApiResource<ProductPortfolioData>("/api/product/portfolio");

  if (loading) return <StatePanel kind="loading" title="正在读取组合分析" description="加载配置持仓、主题暴露和观察性问题。" />;
  if (error) return <StatePanel kind="error" title="组合分析读取失败" description={error} />;
  if (!resource || resource.availability === "missing") {
    return <StatePanel kind="empty" title="尚无组合分析产物" description="完成每日数据更新后再查看。" />;
  }

  const data = resource.data;
  const valuation = data.valuation || {
    state: "unavailable" as const,
    label: "当前估值暂不可用",
    description: "尚未取得完整估值，因此组合汇总暂不可计算。",
    valued_position_count: 0,
    unvalued_position_count: data.holding_count ?? data.positions?.length ?? 0
  };
  const observations = data.observations || [];
  const valuationUnavailable = valuation.state !== "complete";

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="已配置持仓"
        title="组合"
        description="已配置的持仓观察，与自选池相互独立。"
        actions={<StatusBadge tone={valuationUnavailable ? "warning" : "success"}>{valuation.label}</StatusBadge>}
      />

      <section className="metric-grid" aria-label="组合指标">
        <Metric label="组合名称" value={data.portfolio_name || "未命名组合"} detail={`数据日期 ${data.as_of || "--"}`} />
        <Metric label="配置持仓" value={data.holding_count ?? data.positions?.length ?? 0} detail="当前配置中的持仓" />
        <Metric label="当前总值" value={valuationUnavailable ? "暂不可计算" : currency.format(data.total_value || 0)} detail={valuationUnavailable ? valuation.description : "已按当前估值汇总"} />
        <Metric label="可用现金" value={currency.format(data.cash_available || 0)} detail={`待核对事项 ${observations.length}`} />
      </section>

      <section className="content-band" aria-labelledby="positions-title">
        <div className="section-heading"><div><p className="eyebrow">持仓明细</p><h2 id="positions-title">持仓明细</h2></div><WalletCards size={19} aria-hidden /></div>
        <DataTable label="组合持仓数据表" minWidth={880}>
          <thead><tr><th>代码</th><th>名称</th><th>主题</th><th>份额</th><th>成本</th><th>当前值</th><th>收益率</th></tr></thead>
          <tbody>
            {(data.positions || []).map((position) => {
              const missing = position.current_value == null;
              return (
                <tr key={position.code}>
                  <td>{isFundCode(position.code) ? <Link className="fund-record-link" to={`/funds/${position.code}?return_to=${encodeURIComponent("/portfolio")}`}>{position.code}</Link> : <strong>{position.code || "--"}</strong>}</td>
                  <td>{isFundCode(position.code) ? <Link className="fund-record-link" to={`/funds/${position.code}?return_to=${encodeURIComponent("/portfolio")}`}>{position.name || "名称缺失"}</Link> : position.name || "名称缺失"}</td>
                  <td>{position.primary_theme || "未分类"}</td>
                  <td>{position.shares ?? "--"}</td>
                  <td>{currency.format(position.cost_value || 0)}</td>
                  <td>{missing ? "--" : currency.format(position.current_value || 0)}</td>
                  <td>{missing || position.unrealized_return_pct == null ? "--" : `${position.unrealized_return_pct.toFixed(2)}%`}</td>
                </tr>
              );
            })}
          </tbody>
        </DataTable>
      </section>

      <div className="split-grid">
        <section className="content-band" aria-labelledby="theme-exposure-title">
          <div className="section-heading"><div><p className="eyebrow">主题分布</p><h2 id="theme-exposure-title">主题暴露</h2></div><CircleDollarSign size={19} aria-hidden /></div>
          <ExposureList items={data.theme_exposure || {}} unavailable={valuationUnavailable} emptyLabel="当前组合没有可展示的主题暴露。" />
        </section>
        <section className="content-band" aria-labelledby="type-exposure-title">
          <div className="section-heading"><div><p className="eyebrow">类型分布</p><h2 id="type-exposure-title">类型暴露</h2></div><Layers3 size={19} aria-hidden /></div>
          <ExposureList items={data.fund_type_exposure || {}} unavailable={valuationUnavailable} emptyLabel="当前组合没有可展示的基金类型暴露。" />
        </section>
      </div>

      <section className="content-band" aria-labelledby="issues-title">
        <div className="section-heading"><div><p className="eyebrow">需要关注</p><h2 id="issues-title">观察性问题</h2></div><TriangleAlert size={19} aria-hidden /></div>
        <div className="issue-list">
          {observations.length ? observations.map((issue, index) => (
            <div className="issue-item" key={`${issue.title}-${index}`}>
              <StatusBadge tone={issue.tone === "critical" ? "critical" : "warning"}>{issue.tone === "attention" ? "请核对" : "待处理"}</StatusBadge>
              <div><strong>{issue.title}</strong><p>{issue.description}</p></div>
            </div>
          )) : <p className="empty-copy">当前没有待处理的组合观察性问题。</p>}
        </div>
      </section>

      <div className="boundary-band"><strong>组合页不生成调仓动作</strong><p>这里只展示现有配置、数据缺口和观察性风险，不改变主 risk_issues，不输出买卖建议。</p></div>
    </div>
  );
}
