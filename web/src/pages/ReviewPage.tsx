import { ClipboardCheck, Save } from "lucide-react";
import { useState } from "react";

import { postResource } from "../api/client";
import type { ReviewItem, ReviewsData } from "../api/types";
import { Metric } from "../components/Metric";
import { PageHeader } from "../components/PageHeader";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";

const REVIEW_STATUSES = [
  { value: "open", label: "待审核" },
  { value: "needs_more_data", label: "需要更多资料" },
  { value: "approved_for_more_experiment", label: "可继续观察" },
  { value: "rejected", label: "不纳入观察" },
  { value: "approved_for_main_candidate", label: "可进入后续评估" }
];

function reviewStatusLabel(status?: string | null): string {
  return REVIEW_STATUSES.find((item) => item.value === status)?.label || "状态待确认";
}

function reviewReasonLabel(reason?: string | null): string {
  if (reason === "insufficient_history") return "历史样本仍在积累";
  if (reason === "manual_review_required") return "需要人工核对";
  return reason ? "存在一项待人工核对的观察条件" : "未提供复核原因";
}

export function ReviewPage() {
  const { loading, resource, error } = useApiResource<ReviewsData>("/api/reviews");
  const [drafts, setDrafts] = useState<Record<string, { status: string; note: string }>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  if (loading) return <StatePanel kind="loading" title="正在读取人工审核队列" description="加载候选项和已保存的审核记录。" />;
  if (error) return <StatePanel kind="error" title="人工审核暂不可读取" description="请稍后刷新页面。" />;
  if (!resource || resource.availability === "missing") {
    return <StatePanel kind="empty" title="当前没有待审核事项" description="生成 review queue 后可在这里记录人工判断。" />;
  }

  const data = resource.data;
  const queue = data.queue || [];
  const stateById = new Map((data.state || []).map((item) => [item.review_id, item]));

  async function save(item: ReviewItem) {
    const reviewId = item.review_id;
    if (!reviewId) return;
    const existing = stateById.get(reviewId);
    const draft = drafts[reviewId] || { status: existing?.status || item.status || "open", note: existing?.note || "" };
    setSaving(reviewId);
    setMessage(null);
    try {
      const result = await postResource<ReviewItem, { status: string; note: string; signal_id?: string }>(`/api/reviews/${reviewId}`, {
        status: draft.status,
        note: draft.note,
        signal_id: item.signal_id
      });
      setMessage(`审核记录已更新为“${reviewStatusLabel(result.data.status)}”。`);
    } catch (saveError) {
      setMessage("审核记录暂未保存，请稍后再试。");
    } finally {
      setSaving(null);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader eyebrow="人工复核" title="人工审核" description="复核候选观察、资料状态和待补充事项，所有判断均保留审核记录。" actions={<StatusBadge tone="info">人工复核</StatusBadge>} />
      <section className="metric-grid" aria-label="审核指标">
        <Metric label="队列项目" value={queue.length} detail="当前候选事项" />
        <Metric label="审核记录" value={data.summary?.total_review_items || 0} detail="已保存状态" />
        <Metric label="未解决" value={data.summary?.unresolved_count || 0} detail="仍需复核" />
        <Metric label="需要更多数据" value={data.summary?.needs_more_data_count || 0} detail="保持实验层" />
      </section>

      <section className="content-band" aria-labelledby="review-queue-title">
        <div className="section-heading"><div><p className="eyebrow">待处理事项</p><h2 id="review-queue-title">待审核事项</h2></div><ClipboardCheck size={19} aria-hidden /></div>
        <div className="review-list">
          {queue.map((item) => {
            const reviewId = item.review_id || "review-item";
            const existing = stateById.get(reviewId);
            const draft = drafts[reviewId] || { status: existing?.status || item.status || "open", note: existing?.note || "" };
            return (
              <article className="review-item" key={reviewId}>
                <div className="review-item__summary"><div><span>研究候选项</span><h3>待人工复核</h3><p>{reviewReasonLabel(item.reason || item.excluded_reason)}</p></div><StatusBadge tone={draft.status === "rejected" ? "critical" : draft.status === "open" ? "warning" : "info"}>{reviewStatusLabel(draft.status)}</StatusBadge></div>
                <div className="review-controls">
                  <label><span>审核状态</span><select aria-label="审核状态" value={draft.status} onChange={(event) => setDrafts((current) => ({ ...current, [reviewId]: { ...draft, status: event.target.value } }))}>{REVIEW_STATUSES.map((status) => <option key={status.value} value={status.value}>{status.label}</option>)}</select></label>
                  <label className="review-note"><span>审核备注</span><textarea aria-label="审核备注" rows={2} maxLength={2000} value={draft.note} onChange={(event) => setDrafts((current) => ({ ...current, [reviewId]: { ...draft, note: event.target.value } }))} /></label>
                  <button className="secondary-button" type="button" aria-label="保存审核记录" disabled={saving === reviewId} onClick={() => save(item)}><Save size={15} aria-hidden />{saving === reviewId ? "保存中" : "保存"}</button>
                </div>
              </article>
            );
          })}
        </div>
        {message ? <p className="form-message" role="status">{message}</p> : null}
      </section>

      <div className="boundary-band"><strong>审核只记录人工判断</strong><p>不会覆盖主评分、主风险或已生成研究结论，也不会触发交易。</p></div>
    </div>
  );
}
