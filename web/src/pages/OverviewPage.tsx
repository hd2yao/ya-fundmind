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

function qualityLabel(grade?: string | null): string {
  if (grade === "normal" || grade === "good") return "资料已更新";
  if (grade === "critical" || grade === "degraded") return "资料待补充";
  if (grade === "warning") return "请留意数据日期";
  return "状态待确认";
}

function runLabel(status?: string | null): string {
  if (status === "success") return "运行完成";
  if (status === "failed") return "运行未完成";
  if (status === "running") return "正在更新";
  return "状态待确认";
}

export function OverviewPage() {
  const { loading, resource, error } = useApiResource<OverviewData>("/api/overview");

  const header = (
    <PageHeader
      eyebrow="每日更新"
      title="系统状态"
      description="确认最近一次更新、资料状态和需要人工处理的事项。"
    />
  );

  if (loading) {
    return <div className="page-stack">{header}<StatePanel kind="loading" title="正在读取运行状态" description="汇总最近一次更新、资料状态和人工复核队列。" /></div>;
  }
  if (error) {
    return <div className="page-stack">{header}<StatePanel kind="error" title="运行状态暂不可读取" description="请稍后刷新页面。" /></div>;
  }
  if (!resource || resource.availability === "missing") {
    return (
      <div className="page-stack">
        {header}
        <StatePanel
          kind="empty"
          title="尚无可用的每日研究产物"
          description="完成一次日常更新后再查看。"
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
        eyebrow="每日更新"
        title="系统状态"
        description="确认最近一次更新、资料状态和需要人工处理的事项。"
        actions={<StatusBadge tone={ops.ops_ready ? "success" : "critical"}>{ops.ops_ready ? "运行正常" : "需要处理"}</StatusBadge>}
      />

      <section className="metric-grid" aria-label="关键运行指标">
        <Metric label="最新研究日" value={latestRun.as_of || daily.as_of || "--"} detail={runLabel(latestRun.status || daily.status)} />
        <Metric label="资料状态" value={<StatusBadge tone={qualityTone(quality)}>{qualityLabel(quality)}</StatusBadge>} detail="以页面显示的数据日期为准" />
        <Metric label="待复核队列" value={data.review_queue_count ?? 0} detail={`未解决 ${data.review_state_summary?.unresolved_count ?? 0}`} />
        <Metric label="市场主题" value={ops.latest_market_theme_count ?? 0} detail={`自选 ${ops.watchlist_detail_count ?? 0} · 持仓 ${ops.latest_portfolio_holding_count ?? 0}`} />
      </section>

      <section className="content-band" aria-labelledby="run-health-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">运行概览</p>
            <h2 id="run-health-title">运行与研究状态</h2>
          </div>
          {ops.main_model_ready ? <CheckCircle2 size={20} aria-hidden /> : <Clock3 size={20} aria-hidden />}
        </div>
        <div className="status-row">
          <StatusBadge tone={ops.dashboard_ready ? "success" : "warning"}>{ops.dashboard_ready ? "研究页面可用" : "研究页面待补充"}</StatusBadge>
          <StatusBadge tone={ops.main_model_ready ? "success" : "info"}>{ops.main_model_ready ? "研究分析已完成验证" : "研究分析维持观察"}</StatusBadge>
        </div>
        {blockers.length ? (
          <div className="notice notice--info">
            <AlertTriangle size={18} aria-hidden />
            <div>
              <strong>当前仍有观察条件待完成</strong>
              <p>历史样本或人工复核尚在积累，因此研究分析暂不调整；不影响日常更新和页面浏览。</p>
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
