import { ClipboardCheck, Save } from "lucide-react";
import { useState } from "react";

import { postResource } from "../api/client";
import type { ReviewItem, ReviewsData } from "../api/types";
import { Metric } from "../components/Metric";
import { PageHeader } from "../components/PageHeader";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";

const REVIEW_STATUSES = ["open", "needs_more_data", "approved_for_more_experiment", "rejected", "approved_for_main_candidate"];

export function ReviewPage() {
  const { loading, resource, error } = useApiResource<ReviewsData>("/api/reviews");
  const [drafts, setDrafts] = useState<Record<string, { status: string; note: string }>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  if (loading) return <StatePanel kind="loading" title="正在读取人工审核队列" description="加载候选项和已保存的本地 review state。" />;
  if (error) return <StatePanel kind="error" title="人工审核读取失败" description={error} />;
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
      setMessage(`${reviewId} 已更新为 ${result.data.status}`);
    } catch (saveError) {
      setMessage(saveError instanceof Error ? saveError.message : "Review update failed.");
    } finally {
      setSaving(null);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader eyebrow="Human review gate" title="人工审核" description="复核候选信号、证据质量和数据缺口，所有决策保留本地记录。" actions={<StatusBadge tone="info">Manual gate</StatusBadge>} />
      <section className="metric-grid" aria-label="审核指标">
        <Metric label="队列项目" value={queue.length} detail="当前候选事项" />
        <Metric label="审核记录" value={data.summary?.total_review_items || 0} detail="已保存状态" />
        <Metric label="未解决" value={data.summary?.unresolved_count || 0} detail="仍需复核" />
        <Metric label="需要更多数据" value={data.summary?.needs_more_data_count || 0} detail="保持实验层" />
      </section>

      <section className="content-band" aria-labelledby="review-queue-title">
        <div className="section-heading"><div><p className="eyebrow">Review queue</p><h2 id="review-queue-title">待审核事项</h2></div><ClipboardCheck size={19} aria-hidden /></div>
        <div className="review-list">
          {queue.map((item) => {
            const reviewId = item.review_id || "unknown";
            const existing = stateById.get(reviewId);
            const draft = drafts[reviewId] || { status: existing?.status || item.status || "open", note: existing?.note || "" };
            return (
              <article className="review-item" key={reviewId}>
                <div className="review-item__summary"><div><span>{reviewId}</span><h3>{item.signal_id || "未关联 signal"}</h3><p>{item.reason || item.excluded_reason || "未提供复核原因"}</p></div><StatusBadge tone={draft.status === "rejected" ? "critical" : draft.status === "open" ? "warning" : "info"}>{draft.status}</StatusBadge></div>
                <div className="review-controls">
                  <label><span>审核状态</span><select aria-label={`审核状态 ${reviewId}`} value={draft.status} onChange={(event) => setDrafts((current) => ({ ...current, [reviewId]: { ...draft, status: event.target.value } }))}>{REVIEW_STATUSES.map((status) => <option key={status}>{status}</option>)}</select></label>
                  <label className="review-note"><span>审核备注</span><textarea aria-label={`审核备注 ${reviewId}`} rows={2} maxLength={2000} value={draft.note} onChange={(event) => setDrafts((current) => ({ ...current, [reviewId]: { ...draft, note: event.target.value } }))} /></label>
                  <button className="secondary-button" type="button" aria-label={`保存 ${reviewId}`} disabled={saving === reviewId} onClick={() => save(item)}><Save size={15} aria-hidden />{saving === reviewId ? "保存中" : "保存"}</button>
                </div>
              </article>
            );
          })}
        </div>
        {message ? <p className="form-message" role="status">{message}</p> : null}
      </section>

      <div className="boundary-band"><strong>审核只更新本地 review state</strong><p>不会覆盖主评分、主 risk_issues 或已生成研究结论，也不会触发交易。</p></div>
    </div>
  );
}
