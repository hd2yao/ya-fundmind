import { CalendarDays, Clock3, Database, ShieldAlert } from "lucide-react";

import { StatusBadge, type StatusTone } from "./StatusBadge";

function formatTimestamp(value?: string | null) {
  if (!value) return "--";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(parsed);
}

function freshnessTone(stale: boolean, fallbackUsed: boolean, grade?: string | null): StatusTone {
  if (stale || fallbackUsed || grade === "warning") return "warning";
  if (grade === "degraded" || grade === "critical") return "critical";
  return "success";
}

export function DataFreshnessStrip({
  label = "数据新鲜度",
  asOf,
  updatedAt,
  expiresAt,
  source,
  stale = false,
  fallbackUsed = false,
  dataQualityGrade,
  compact = false
}: {
  label?: string;
  asOf?: string | null;
  updatedAt?: string | null;
  expiresAt?: string | null;
  source?: string | null;
  stale?: boolean;
  fallbackUsed?: boolean;
  dataQualityGrade?: string | null;
  compact?: boolean;
}) {
  const status = stale ? "缓存已过期" : fallbackUsed ? "缓存回退" : "本地数据可用";
  return (
    <section className={`data-freshness${compact ? " data-freshness--compact" : ""}`} aria-label={label}>
      <div className="data-freshness__heading">
        <div>
          <span>{label}</span>
          <strong>{status}</strong>
        </div>
        <StatusBadge tone={freshnessTone(stale, fallbackUsed, dataQualityGrade)}>
          {stale || fallbackUsed ? "需要留意" : dataQualityGrade || "normal"}
        </StatusBadge>
      </div>
      <dl className="data-freshness__facts">
        <div>
          <dt><CalendarDays size={14} aria-hidden />交易日</dt>
          <dd>{asOf || "--"}</dd>
        </div>
        <div>
          <dt><Clock3 size={14} aria-hidden />同步于</dt>
          <dd>{formatTimestamp(updatedAt)}</dd>
        </div>
        <div>
          <dt><Clock3 size={14} aria-hidden />缓存有效至</dt>
          <dd>{formatTimestamp(expiresAt)}</dd>
        </div>
        <div>
          <dt><Database size={14} aria-hidden />数据源</dt>
          <dd>{source || "--"}</dd>
        </div>
      </dl>
      {stale || fallbackUsed ? (
        <p className="data-freshness__warning">
          <ShieldAlert size={15} aria-hidden />
          {stale ? "当前展示的是过期缓存。" : "本次未取得 live 数据，展示缓存回退。"}
        </p>
      ) : null}
    </section>
  );
}
