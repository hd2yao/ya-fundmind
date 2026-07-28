import { ExternalLink, Newspaper, ShieldQuestion } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type { NewsData } from "../api/types";
import { FilterBar } from "../components/FilterBar";
import { Metric } from "../components/Metric";
import { PageHeader } from "../components/PageHeader";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";

const ALL_THEMES = "全部主题";
const ALL_QUALITIES = "全部来源质量";
const ALL_STRENGTHS = "全部证据强度";

function isFundCode(value: string): boolean {
  return /^\d{6}$/.test(value);
}

function safeExternalUrl(value?: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString() : null;
  } catch {
    return null;
  }
}

function qualityTone(item: { source_quality?: string | null; low_confidence?: boolean }) {
  if (item.low_confidence || item.source_quality === "low_confidence") return "warning" as const;
  if (item.source_quality === "verified") return "success" as const;
  return "neutral" as const;
}

export function NewsPage() {
  const { loading, resource, error } = useApiResource<NewsData>("/api/news");
  const [query, setQuery] = useState("");
  const [theme, setTheme] = useState(ALL_THEMES);
  const [sourceQuality, setSourceQuality] = useState(ALL_QUALITIES);
  const [evidenceStrength, setEvidenceStrength] = useState(ALL_STRENGTHS);

  const items = resource?.data.items || [];
  const themes = useMemo(() => [ALL_THEMES, ...Array.from(new Set(items.flatMap((item) => item.related_themes || []))).sort()], [items]);
  const sourceQualities = useMemo(() => [ALL_QUALITIES, ...Array.from(new Set(items.map((item) => item.source_quality || "unknown"))).sort()], [items]);
  const evidenceStrengths = useMemo(() => [ALL_STRENGTHS, ...Array.from(new Set(items.map((item) => item.evidence_strength || "unknown"))).sort()], [items]);
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return items.filter((item) => {
      const matchesText = !normalized || `${item.title || ""} ${item.source || ""} ${(item.related_funds || []).join(" ")}`.toLowerCase().includes(normalized);
      const matchesTheme = theme === ALL_THEMES || item.related_themes?.includes(theme);
      const matchesQuality = sourceQuality === ALL_QUALITIES || (item.source_quality || "unknown") === sourceQuality;
      const matchesStrength = evidenceStrength === ALL_STRENGTHS || (item.evidence_strength || "unknown") === evidenceStrength;
      return matchesText && matchesTheme && matchesQuality && matchesStrength;
    });
  }, [items, query, theme, sourceQuality, evidenceStrength]);

  if (loading) return <StatePanel kind="loading" title="正在读取新闻证据" description="加载本地新闻/公告 evidence 与来源质量。" />;
  if (error) return <StatePanel kind="error" title="新闻证据读取失败" description={error} />;
  if (!resource || resource.availability === "missing") {
    return <StatePanel kind="empty" title="尚无新闻证据产物" description="配置允许的数据源并运行 news evidence 流程后再查看。" />;
  }

  const data = resource.data;
  const fixtureEvidence = data.source?.includes("fixture") || items.some((item) => item.source?.includes("fixture"));
  const indexedFundCodes = new Set(data.indexed_fund_codes || []);

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="News and announcements"
        title="研究证据"
        description="按来源、主题和基金核对新闻/公告证据。低置信度或缺 URL 的条目必须人工复核。"
        actions={fixtureEvidence ? <StatusBadge tone="warning">Fixture evidence</StatusBadge> : <StatusBadge tone="info">Evidence only</StatusBadge>}
      />

      <section className="metric-grid" aria-label="新闻证据指标">
        <Metric label="证据总数" value={data.evidence_count ?? items.length} detail={`as_of ${data.as_of || "--"}`} />
        <Metric label="低置信度" value={data.low_confidence_count ?? 0} detail="默认需要人工复核" />
        <Metric label="重复项" value={data.duplicate_count ?? 0} detail="去重后输出" />
        <Metric label="当前筛选" value={filtered.length} detail={`${items.length} 条本地 evidence 中匹配`} />
      </section>

      <section className="content-band" aria-labelledby="evidence-list-title">
        <div className="section-heading"><div><p className="eyebrow">Evidence stream</p><h2 id="evidence-list-title">证据列表</h2></div><Newspaper size={19} aria-hidden /></div>
        <FilterBar
          searchLabel="搜索标题、来源或基金代码"
          searchValue={query}
          onSearchChange={setQuery}
          selectLabel="按主题筛选"
          selectValue={theme}
          selectOptions={themes}
          onSelectChange={setTheme}
          additionalSelects={[
            { label: "按来源质量筛选", value: sourceQuality, options: sourceQualities, onChange: setSourceQuality },
            { label: "按证据强度筛选", value: evidenceStrength, options: evidenceStrengths, onChange: setEvidenceStrength }
          ]}
        />
        <div className="evidence-list">
          {filtered.length ? filtered.map((item) => {
            const externalUrl = safeExternalUrl(item.url);
            return (
            <article className="evidence-item" key={item.evidence_id}>
              <div className="evidence-meta">
                <StatusBadge tone={qualityTone(item)}>{item.source_quality || "unknown"}</StatusBadge>
                <StatusBadge tone={item.evidence_strength === "low" ? "warning" : "neutral"}>{item.evidence_strength || "unknown"}</StatusBadge>
                <span>{item.published_at ? new Date(item.published_at).toLocaleString("zh-CN") : "时间缺失"}</span>
                <span>{item.source || "来源缺失"}</span>
              </div>
              <h3>{item.title || "标题缺失"}</h3>
              <div className="tag-row">
                {(item.related_themes || []).map((value) => <span className="tag" key={value}>{value}</span>)}
                {(item.related_funds || []).map((value) => (
                  isFundCode(value) && indexedFundCodes.has(value)
                    ? <Link className="tag tag--code fund-evidence-link" key={value} to={`/funds/${value}?return_to=${encodeURIComponent("/news")}`}>{value}</Link>
                    : <span className="tag tag--code tag--muted" key={value} title="该关联基金不在当前本地基金索引中，不能打开详情。">{isFundCode(value) ? `${value} · 未索引` : `${value} · 代码无效`}</span>
                ))}
              </div>
              <div className="evidence-footer">
                {item.low_confidence && item.source_quality !== "low_confidence" ? <StatusBadge tone="warning">low_confidence</StatusBadge> : null}
                {(item.warnings || []).map((warning) => <span className="tag tag--muted" key={warning}>{warning}</span>)}
                {externalUrl ? (
                  <a className="external-link" href={externalUrl} target="_blank" rel="noopener noreferrer">打开来源 <ExternalLink size={14} aria-hidden /></a>
                ) : <span className="missing-link">{item.url ? "链接不可安全打开" : "没有可核验链接"}</span>}
              </div>
            </article>
            );
          }) : <p className="empty-copy">没有符合当前筛选的证据。请调整文本、主题、来源质量或证据强度。</p>}
        </div>
      </section>

      <div className="notice">
        <ShieldQuestion size={18} aria-hidden />
        <div><strong>新闻是证据，不是信号结论</strong><p>Fixture、unknown source、low confidence 或 missing URL 不得作为独立正向依据。</p></div>
      </div>
    </div>
  );
}
