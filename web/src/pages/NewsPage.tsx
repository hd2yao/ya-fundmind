import { ExternalLink, Newspaper, ShieldQuestion } from "lucide-react";
import { useMemo, useState } from "react";

import type { NewsData } from "../api/types";
import { FilterBar } from "../components/FilterBar";
import { Metric } from "../components/Metric";
import { PageHeader } from "../components/PageHeader";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge } from "../components/StatusBadge";
import { useApiResource } from "../hooks/useApiResource";

export function NewsPage() {
  const { loading, resource, error } = useApiResource<NewsData>("/api/news");
  const [query, setQuery] = useState("");
  const [theme, setTheme] = useState("全部主题");

  const items = resource?.data.items || [];
  const themes = useMemo(() => ["全部主题", ...Array.from(new Set(items.flatMap((item) => item.related_themes || []))).sort()], [items]);
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return items.filter((item) => {
      const matchesText = !normalized || `${item.title || ""} ${item.source || ""} ${(item.related_funds || []).join(" ")}`.toLowerCase().includes(normalized);
      const matchesTheme = theme === "全部主题" || item.related_themes?.includes(theme);
      return matchesText && matchesTheme;
    });
  }, [items, query, theme]);

  if (loading) return <StatePanel kind="loading" title="正在读取新闻证据" description="加载本地新闻/公告 evidence 与来源质量。" />;
  if (error) return <StatePanel kind="error" title="新闻证据读取失败" description={error} />;
  if (!resource || resource.availability === "missing") {
    return <StatePanel kind="empty" title="尚无新闻证据产物" description="配置允许的数据源并运行 news evidence 流程后再查看。" />;
  }

  const data = resource.data;
  const fixtureEvidence = data.source?.includes("fixture") || items.some((item) => item.source?.includes("fixture"));

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="News and announcements"
        title="新闻证据"
        description="按来源、主题和基金核对新闻/公告证据。低置信度或缺 URL 的条目必须人工复核。"
        actions={fixtureEvidence ? <StatusBadge tone="warning">Fixture evidence</StatusBadge> : <StatusBadge tone="info">Evidence only</StatusBadge>}
      />

      <section className="metric-grid" aria-label="新闻证据指标">
        <Metric label="证据总数" value={data.evidence_count ?? items.length} detail={`as_of ${data.as_of || "--"}`} />
        <Metric label="低置信度" value={data.low_confidence_count ?? 0} detail="默认需要人工复核" />
        <Metric label="重复项" value={data.duplicate_count ?? 0} detail="去重后输出" />
        <Metric label="当前筛选" value={filtered.length} detail={`${themes.length - 1} 个关联主题`} />
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
        />
        <div className="evidence-list">
          {filtered.map((item) => (
            <article className="evidence-item" key={item.evidence_id}>
              <div className="evidence-meta">
                <StatusBadge tone={item.low_confidence ? "warning" : "success"}>{item.source_quality || "unknown"}</StatusBadge>
                <span>{item.published_at ? new Date(item.published_at).toLocaleString("zh-CN") : "时间缺失"}</span>
                <span>{item.source || "来源缺失"}</span>
              </div>
              <h3>{item.title || "标题缺失"}</h3>
              <div className="tag-row">
                {(item.related_themes || []).map((value) => <span className="tag" key={value}>{value}</span>)}
                {(item.related_funds || []).map((value) => <span className="tag tag--code" key={value}>{value}</span>)}
              </div>
              <div className="evidence-footer">
                <span>strength={item.evidence_strength || "unknown"}</span>
                {item.low_confidence && item.source_quality !== "low_confidence" ? <StatusBadge tone="warning">low_confidence</StatusBadge> : null}
                {item.url ? (
                  <a className="external-link" href={item.url} target="_blank" rel="noreferrer">打开来源 <ExternalLink size={14} aria-hidden /></a>
                ) : <span className="missing-link">没有可核验链接</span>}
              </div>
            </article>
          ))}
        </div>
      </section>

      <div className="notice">
        <ShieldQuestion size={18} aria-hidden />
        <div><strong>新闻是证据，不是信号结论</strong><p>Fixture、unknown source、low confidence 或 missing URL 不得作为独立正向依据。</p></div>
      </div>
    </div>
  );
}
