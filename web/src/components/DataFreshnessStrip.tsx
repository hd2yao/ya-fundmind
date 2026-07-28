import { CalendarDays, Clock3, ShieldAlert } from "lucide-react";

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

export function getDataCondition({
  stale = false,
  fallbackUsed = false,
  dataQualityGrade
}: {
  stale?: boolean;
  fallbackUsed?: boolean;
  dataQualityGrade?: string | null;
}): { label: string; tone: StatusTone; message?: string } {
  if (stale) {
    return {
      label: "数据需核对",
      tone: "warning",
      message: "当前数据不是最新，请以更新时间为准。"
    };
  }
  if (fallbackUsed) {
    return {
      label: "数据需核对",
      tone: "warning",
      message: "暂未取得新数据，当前展示最近一次可用记录。"
    };
  }
  if (dataQualityGrade === "degraded" || dataQualityGrade === "critical") {
    return {
      label: "数据需核对",
      tone: "critical",
      message: "部分数据暂不完整，请结合更新时间和详情判断。"
    };
  }
  return { label: "数据更新正常", tone: "success" };
}

type DataFreshnessStripProps = {
  label?: string;
  asOf?: string | null;
  updatedAt?: string | null;
  expiresAt?: string | null;
  source?: string | null;
  stale?: boolean;
  fallbackUsed?: boolean;
  dataQualityGrade?: string | null;
  compact?: boolean;
  showDiagnostics?: boolean;
};

export function DataFreshnessStrip({
  label = "数据新鲜度",
  asOf,
  updatedAt,
  expiresAt,
  stale = false,
  fallbackUsed = false,
  dataQualityGrade,
  compact = false,
  showDiagnostics = false
}: DataFreshnessStripProps) {
  const condition = getDataCondition({ stale, fallbackUsed, dataQualityGrade });
  return (
    <section className={`data-freshness${compact ? " data-freshness--compact" : ""}`} aria-label={label}>
      <div className="data-freshness__heading">
        <div>
          <span>{label}</span>
          <strong>{condition.label}</strong>
        </div>
        <StatusBadge tone={condition.tone}>{condition.label}</StatusBadge>
      </div>
      <dl className="data-freshness__facts">
        <div>
          <dt><CalendarDays size={14} aria-hidden />数据日期</dt>
          <dd>{asOf || "--"}</dd>
        </div>
        <div>
          <dt><Clock3 size={14} aria-hidden />更新于</dt>
          <dd>{formatTimestamp(updatedAt)}</dd>
        </div>
        {showDiagnostics ? (
          <div>
            <dt><Clock3 size={14} aria-hidden />诊断有效期</dt>
            <dd>{formatTimestamp(expiresAt)}</dd>
          </div>
        ) : null}
      </dl>
      {condition.message ? (
        <p className="data-freshness__warning">
          <ShieldAlert size={15} aria-hidden />
          {condition.message}
        </p>
      ) : null}
    </section>
  );
}
