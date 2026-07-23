import { AlertTriangle, CheckCircle2, Clock3 } from "lucide-react";

import type { OverviewData } from "../api/types";
import { Metric } from "../components/Metric";
import { PageHeader } from "../components/PageHeader";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge, type StatusTone } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";

function qualityTone(grade?: string | null): StatusTone {
  if (grade === "normal" || grade === "good") return "success";
  if (grade === "critical" || grade === "degraded") return "critical";
  if (grade === "warning") return "warning";
  return "neutral";
}

export function OverviewPage() {
  const { loading, resource, error } = useApiResource<OverviewData>("/api/overview");

  const header = (
    <PageHeader
      eyebrow="Daily research pulse"
      title="系统状态"
      description="确认最新运行、数据质量和需要人工处理的事项。所有指标来自本地结构化产物。"
    />
  );

  if (loading) {
    return <div className="page-stack">{header}<StatePanel kind="loading" title="正在读取本地研究状态" description="汇总最新 daily、数据质量和人工复核队列。" /></div>;
  }
  if (error) {
    return <div className="page-stack">{header}<StatePanel kind="error" title="无法连接本地研究 API" description={error} /></div>;
  }
  if (!resource || resource.availability === "missing") {
    return (
      <div className="page-stack">
        {header}
        <StatePanel
          kind="empty"
          title="尚无可用的每日研究产物"
          description="先运行 PROVIDER=akshare ENABLE_MARKET_INTELLIGENCE=true scripts/run_daily_ops.sh。"
        />
      </div>
    );
  }

  const data = resource.data;
  const ops = data.ops_status || {};
  const daily = ops.daily || {};
  const latestRun = ops.latest_run || {};
  const quality = daily.data_quality_grade || "unknown";
  const blockers = ops.main_model_blockers || [];

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Daily research pulse"
        title="系统状态"
        description="确认最新运行、数据质量和需要人工处理的事项。所有指标来自本地结构化产物。"
        actions={<StatusBadge tone={ops.ops_ready ? "success" : "critical"}>{ops.ops_ready ? "Daily ready" : "Daily blocked"}</StatusBadge>}
      />

      <section className="metric-grid" aria-label="关键运行指标">
        <Metric label="最新研究日" value={latestRun.as_of || daily.as_of || "--"} detail={latestRun.status || daily.status || "暂无状态"} />
        <Metric label="数据质量" value={<StatusBadge tone={qualityTone(quality)}>{quality}</StatusBadge>} detail="保留 warning / stale 标记" />
        <Metric label="待复核队列" value={data.review_queue_count ?? 0} detail={`未解决 ${data.review_state_summary?.unresolved_count ?? 0}`} />
        <Metric label="市场主题" value={ops.latest_market_theme_count ?? 0} detail={`自选 ${ops.watchlist_detail_count ?? 0} · 持仓 ${ops.latest_portfolio_holding_count ?? 0}`} />
      </section>

      <section className="content-band" aria-labelledby="run-health-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Operational health</p>
            <h2 id="run-health-title">运行与模型门禁</h2>
          </div>
          {ops.main_model_ready ? <CheckCircle2 size={20} aria-hidden /> : <Clock3 size={20} aria-hidden />}
        </div>
        <div className="status-row">
          <StatusBadge tone={ops.dashboard_ready ? "success" : "warning"}>Dashboard {ops.dashboard_ready ? "ready" : "missing"}</StatusBadge>
          <StatusBadge tone={ops.main_model_ready ? "success" : "info"}>主模型 {ops.main_model_ready ? "ready" : "research only"}</StatusBadge>
        </div>
        {blockers.length ? (
          <div className="notice notice--info">
            <AlertTriangle size={18} aria-hidden />
            <div>
              <strong>当前门禁：<code>{blockers.join(" · ")}</code></strong>
              <p>该门禁仅阻塞主模型升级，不影响 daily、dashboard 和本地研究页面正常使用。</p>
            </div>
          </div>
        ) : null}
      </section>

      <section className="boundary-band">
        <strong>研究边界保持不变</strong>
        <p>主评分未修改，主风险未修改；不自动交易、不接券商、不输出买卖建议或收益承诺。</p>
      </section>
    </div>
  );
}
