import { BookOpenText, MessageSquareText, Send, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";

import { postResource } from "../api/client";
import type { CopilotResponseData } from "../api/types";
import { Metric } from "../components/Metric";
import { PageHeader } from "../components/PageHeader";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge } from "../components/StatusBadge";

const EXAMPLES = [
  "当前市场热点和主要证据是什么？",
  "自选基金中哪些数据需要人工复核？",
  "当前组合有哪些已知的数据缺口？"
];

function valueText(value: unknown) {
  if (value === null || value === undefined) return "--";
  if (typeof value === "string" || typeof value === "number") return String(value);
  return JSON.stringify(value);
}

export function CopilotPage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<CopilotResponseData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const normalized = question.trim();
    if (!normalized) {
      setError("请输入研究问题。");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const resource = await postResource<CopilotResponseData, { question: string }>("/api/copilot/ask", { question: normalized });
      setAnswer(resource.data);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Research Copilot request failed.");
    } finally {
      setLoading(false);
    }
  }

  const view = answer?.view_model;
  const tone = view?.status === "answered" ? "success" : view?.status === "refused" ? "critical" : "warning";

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Evidence-grounded copilot"
        title="研究助手"
        description="只读取本地结构化研究产物，并为结论附上证据来源、时间和质量。"
        actions={<StatusBadge tone="info">Read-only research</StatusBadge>}
      />

      <section className="copilot-layout">
        <form className="copilot-composer" onSubmit={submit}>
          <label htmlFor="copilot-question">研究问题</label>
          <textarea
            id="copilot-question"
            value={question}
            maxLength={1000}
            rows={5}
            placeholder="例如：半导体主题近期有哪些变化和证据？"
            onChange={(event) => setQuestion(event.target.value)}
          />
          <div className="example-row" aria-label="示例问题">
            {EXAMPLES.map((example) => (
              <button className="example-chip" type="button" key={example} onClick={() => setQuestion(example)}>{example}</button>
            ))}
          </div>
          <div className="composer-footer">
            <span>{question.length}/1000</span>
            <button className="primary-button" type="submit" disabled={loading}>
              <Send size={16} aria-hidden /> {loading ? "正在读取证据" : "生成证据化回答"}
            </button>
          </div>
          {error ? <p className="form-error" role="alert">{error}</p> : null}
        </form>

        <aside className="copilot-boundary">
          <ShieldCheck size={20} aria-hidden />
          <div><strong>当前回答不改变主评分或主风险</strong><p>证据不足时会 partial、refused 或列出 data gap，不生成交易动作。</p></div>
        </aside>
      </section>

      {view ? (
        <div className="page-stack">
          <section className="metric-grid" aria-label="回答指标">
            <Metric label="回答状态" value={<StatusBadge tone={tone}>{view.status || "unknown"}</StatusBadge>} detail={`as_of ${view.as_of || "--"}`} />
            <Metric label="研究意图" value={view.intent || "--"} detail="本地意图分类" />
            <Metric label="置信度" value={view.confidence || "low"} detail={view.review_required ? "需要人工复核" : "无需额外复核"} />
            <Metric label="证据数量" value={view.evidence_count || 0} detail={`结论 ${view.finding_count || 0}`} />
          </section>

          <section className="content-band" aria-labelledby="copilot-summary-title">
            <div className="section-heading"><div><p className="eyebrow">Research answer</p><h2 id="copilot-summary-title">研究摘要</h2></div><MessageSquareText size={19} aria-hidden /></div>
            <p className="answer-summary">{view.summary || "没有可用摘要。"}</p>
          </section>

          <section className="finding-list" aria-label="研究结论与证据">
            {(view.findings || []).map((finding, index) => (
              <article className="finding-item" key={finding.finding_id || index}>
                <div className="finding-header"><div><span>Finding {index + 1}</span><h3>{finding.label || finding.finding_id || "未命名结论"}</h3></div><StatusBadge tone={finding.quality_grade === "normal" ? "success" : "warning"}>{finding.quality_grade || "unknown"}</StatusBadge></div>
                <p>{valueText(finding.value)}</p>
                <div className="citation-list">
                  {(finding.citations || []).map((citation) => (
                    <div className="citation-item" key={citation.evidence_id}>
                      <BookOpenText size={17} aria-hidden />
                      <div><strong>{citation.source || "unknown"}</strong><span>{citation.evidence_id || "evidence"} · {citation.as_of || "--"} · quality={citation.quality_grade || "unknown"} · stale={String(Boolean(citation.stale))}</span></div>
                    </div>
                  ))}
                </div>
              </article>
            ))}
          </section>

          {(view.data_gaps || []).length ? (
            <StatePanel kind="degraded" title="数据缺口" description={(view.data_gaps || []).join(" · ")} />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
