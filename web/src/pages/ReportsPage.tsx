import { ArrowUpRight, FileCheck2, FileClock } from "lucide-react";

import type { ReportsData } from "../api/types";
import { PageHeader } from "../components/PageHeader";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";

export function ReportsPage() {
  const { loading, resource, error } = useApiResource<ReportsData>("/api/reports");

  if (loading) return <StatePanel kind="loading" title="正在读取报告目录" description="检查允许列表内的本地报告产物。" />;
  if (error) return <StatePanel kind="error" title="报告目录读取失败" description={error} />;
  if (!resource || resource.availability === "missing") {
    return <StatePanel kind="empty" title="尚无可用报告" description="运行 daily ops 后生成最新摘要、主报告与 dashboard。" />;
  }

  const reports = resource.data.reports || [];
  const available = reports.filter((item) => item.exists).length;

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Generated artifacts" title="报告中心" description="浏览 allowlist 内的本地人类可读报告；下游集成使用 JSON contract。" actions={<StatusBadge tone="success">{available}/{reports.length} ready</StatusBadge>} />
      <section className="report-grid" aria-label="本地报告">
        {reports.map((report) => (
          <article className="report-item" key={report.report_id}>
            <div className={`report-icon${report.exists ? " report-icon--ready" : ""}`}>{report.exists ? <FileCheck2 size={21} aria-hidden /> : <FileClock size={21} aria-hidden />}</div>
            <div className="report-copy"><span>{report.kind.toUpperCase()}</span><h2>{report.label}</h2><code>{report.relative_path}</code><p>{report.exists ? `更新于 ${report.updated_at ? new Date(report.updated_at).toLocaleString("zh-CN") : "未知时间"}` : "尚未生成"}</p></div>
            {report.exists ? <a className="icon-button" aria-label={`打开${report.label}`} title={`打开${report.label}`} href={`/api/reports/${report.report_id}`} target="_blank" rel="noreferrer"><ArrowUpRight size={18} aria-hidden /></a> : null}
          </article>
        ))}
      </section>
      <div className="notice notice--info"><FileCheck2 size={18} aria-hidden /><div><strong>人类报告与机器 contract 分离</strong><p>下游集成只读取 JSON contract，不解析 Markdown；此页面仅用于打开人类可读报告。</p></div></div>
    </div>
  );
}
