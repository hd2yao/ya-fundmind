import { ArrowUpRight, FileCheck2, FileClock } from "lucide-react";

import type { ReportsData } from "../api/types";
import { PageHeader } from "../components/PageHeader";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";

function reportKindLabel(kind: string): string {
  if (kind.toLowerCase() === "html") return "网页报告";
  if (kind.toLowerCase() === "md") return "文本摘要";
  return "研究报告";
}

export function ReportsPage() {
  const { loading, resource, error } = useApiResource<ReportsData>("/api/reports");

  if (loading) return <StatePanel kind="loading" title="正在读取报告目录" description="整理已生成的研究报告。" />;
  if (error) return <StatePanel kind="error" title="报告目录暂不可读取" description="请稍后刷新页面。" />;
  if (!resource || resource.availability === "missing") {
    return <StatePanel kind="empty" title="尚无可用报告" description="完成一次日常更新后，会在这里生成最新摘要和研究报告。" />;
  }

  const reports = resource.data.reports || [];
  const available = reports.filter((item) => item.exists).length;

  return (
    <div className="page-stack">
      <PageHeader eyebrow="研究成果" title="报告中心" description="浏览已生成的日报、周报和基金研究报告。" actions={<StatusBadge tone="success">已生成 {available} / {reports.length}</StatusBadge>} />
      <section className="report-grid" aria-label="研究报告">
        {reports.map((report) => (
          <article className="report-item" key={report.report_id}>
            <div className={`report-icon${report.exists ? " report-icon--ready" : ""}`}>{report.exists ? <FileCheck2 size={21} aria-hidden /> : <FileClock size={21} aria-hidden />}</div>
            <div className="report-copy"><span>{reportKindLabel(report.kind)}</span><h2>{report.label}</h2><p>{report.exists ? `更新于 ${report.updated_at ? new Date(report.updated_at).toLocaleString("zh-CN") : "未知时间"}` : "尚未生成"}</p></div>
            {report.exists ? <a className="icon-button" aria-label={`打开${report.label}`} title={`打开${report.label}`} href={`/api/reports/${report.report_id}`} target="_blank" rel="noreferrer"><ArrowUpRight size={18} aria-hidden /></a> : null}
          </article>
        ))}
      </section>
      <div className="notice notice--info"><FileCheck2 size={18} aria-hidden /><div><strong>报告用于阅读和人工复核</strong><p>每份报告都保留生成时间，便于对照当天的市场与基金资料。</p></div></div>
    </div>
  );
}
