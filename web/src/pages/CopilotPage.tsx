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

function answerStatusLabel(status?: string | null): string {
  if (status === "answered") return "已生成观察摘要";
  if (status === "partial") return "资料待补充";
  if (status === "refused") return "暂不生成摘要";
  return "状态待确认";
}

function confidenceLabel(confidence?: string | null): string {
  if (confidence === "high") return "较高";
  if (confidence === "medium") return "一般";
  return "需人工核对";
}

function intentLabel(intent?: string | null): string {
  if (intent === "market_overview") return "市场概览";
  if (intent === "watchlist") return "自选观察";
  if (intent === "portfolio") return "组合观察";
  return "研究观察";
}

function findingQualityLabel(quality?: string | null): string {
  if (quality === "normal" || quality === "good") return "资料已更新";
  if (quality === "warning" || quality === "partial") return "请人工核对";
  return "资料待补充";
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
      setError("研究摘要暂不可生成，请稍后再试。");
    } finally {
      setLoading(false);
    }
  }

  const view = answer?.view_model;
  const tone = view?.status === "answered" ? "success" : view?.status === "refused" ? "critical" : "warning";

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="研究辅助"
        title="研究助手"
        description="基于已有研究资料整理观察摘要，并提示需要人工核对的内容。"
        actions={<StatusBadge tone="info">仅作研究观察</StatusBadge>}
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
          <div><strong>当前回答不改变主评分或主风险</strong><p>资料不足时会明确提示人工核对，不生成交易动作。</p></div>
        </aside>
      </section>

      {view ? (
        <div className="page-stack">
          <section className="metric-grid" aria-label="回答指标">
            <Metric label="回答状态" value={<StatusBadge tone={tone}>{answerStatusLabel(view.status)}</StatusBadge>} detail={`数据日期 ${view.as_of || "--"}`} />
            <Metric label="研究范围" value={intentLabel(view.intent)} detail="根据当前问题整理" />
            <Metric label="参考程度" value={confidenceLabel(view.confidence)} detail={view.review_required ? "需要人工复核" : "当前无需额外复核"} />
            <Metric label="证据数量" value={view.evidence_count || 0} detail={`结论 ${view.finding_count || 0}`} />
          </section>

          <section className="content-band" aria-labelledby="copilot-summary-title">
            <div className="section-heading"><div><p className="eyebrow">研究摘要</p><h2 id="copilot-summary-title">研究摘要</h2></div><MessageSquareText size={19} aria-hidden /></div>
            <p className="answer-summary">{view.summary || "没有可用摘要。"}</p>
          </section>

          <section className="finding-list" aria-label="研究结论与证据">
            {(view.findings || []).map((finding, index) => (
              <article className="finding-item" key={finding.finding_id || index}>
                <div className="finding-header"><div><span>观察 {index + 1}</span><h3>{finding.label || "研究观察"}</h3></div><StatusBadge tone={finding.quality_grade === "normal" ? "success" : "warning"}>{findingQualityLabel(finding.quality_grade)}</StatusBadge></div>
                <p>{valueText(finding.value)}</p>
                <div className="citation-list">
                  {(finding.citations || []).map((citation) => (
                    <div className="citation-item" key={citation.evidence_id}>
                      <BookOpenText size={17} aria-hidden />
                      <div><strong>参考资料</strong><span>资料日期 {citation.as_of || "--"}</span></div>
                    </div>
                  ))}
                </div>
              </article>
            ))}
          </section>

          {(view.data_gaps || []).length ? (
            <StatePanel kind="degraded" title="资料待补充" description="当前资料不足以支持更完整的研究摘要，请结合实际信息进行人工核对。" />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
