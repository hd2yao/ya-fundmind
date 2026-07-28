import { ArrowLeft, CircleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { getFundDetail, getFundHistory } from "../api/client";
import type { FundDetailResponse, FundHistoryResponse, FundHistoryWindow } from "../api/types";
import { DataFreshnessStrip } from "../components/DataFreshnessStrip";
import { FundNavChart } from "../components/FundNavChart";
import { Metric } from "../components/Metric";
import { PageHeader } from "../components/PageHeader";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge, type StatusTone } from "../components/StatusBadge";

type DetailState = { loading: boolean; data: FundDetailResponse | null; error: string | null };
type HistoryState = { loading: boolean; data: FundHistoryResponse | null; error: string | null };

const HISTORY_WINDOWS: Array<{ value: FundHistoryWindow; label: string }> = [
  { value: "1m", label: "1 月" },
  { value: "3m", label: "3 月" },
  { value: "6m", label: "6 月" },
  { value: "1y", label: "1 年" },
  { value: "all", label: "全部" }
];

function formatReturn(value?: number | null) {
  if (value == null) return "--";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatNumber(value?: number | null, digits = 2) {
  if (value == null) return "--";
  return value.toLocaleString("zh-CN", { maximumFractionDigits: digits });
}

function qualityTone(quality?: string | null): StatusTone {
  if (quality === "normal" || quality === "complete") return "success";
  if (quality === "degraded" || quality === "critical") return "critical";
  if (quality === "warning" || quality === "partial") return "warning";
  return "neutral";
}

function safeReturnTo(value: string | null): string {
  if (!value || !value.startsWith("/funds") || value.startsWith("//")) return "/funds";
  return value;
}

export function FundDetailPage() {
  const { code = "" } = useParams();
  const location = useLocation();
  const validCode = /^\d{6}$/.test(code);
  const returnTo = safeReturnTo(new URLSearchParams(location.search).get("return_to"));
  const [detail, setDetail] = useState<DetailState>({ loading: true, data: null, error: null });
  const [historyWindow, setHistoryWindow] = useState<FundHistoryWindow>("6m");
  const [history, setHistory] = useState<HistoryState>({ loading: true, data: null, error: null });

  useEffect(() => {
    if (!validCode) return undefined;
    const controller = new AbortController();
    setDetail({ loading: true, data: null, error: null });
    getFundDetail(code, controller.signal)
      .then((data) => setDetail({ loading: false, data, error: null }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setDetail({ loading: false, data: null, error: error instanceof Error ? error.message : "基金详情读取失败。" });
        }
      });
    return () => controller.abort();
  }, [code, validCode]);

  useEffect(() => {
    if (!validCode) return undefined;
    const controller = new AbortController();
    setHistory({ loading: true, data: null, error: null });
    getFundHistory(code, historyWindow, controller.signal)
      .then((data) => setHistory({ loading: false, data, error: null }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setHistory({ loading: false, data: null, error: error instanceof Error ? error.message : "历史净值读取失败。" });
        }
      });
    return () => controller.abort();
  }, [code, historyWindow, validCode]);

  if (!validCode) {
    return <StatePanel kind="error" title="基金代码无效" description="基金详情仅支持六位、已索引的基金代码。" />;
  }

  if (detail.loading) {
    return <StatePanel kind="loading" title="正在读取基金详情" description="读取本地全市场索引与已有研究补充字段。" />;
  }
  if (detail.error || !detail.data) {
    return <StatePanel kind="error" title="基金详情暂不可用" description={detail.error || "本地索引未返回该基金。"} />;
  }

  const { fund, research_detail: research } = detail.data;
  const missingFields = research.missing_fields || [];
  const latest = history.data?.points.at(-1);
  const primarySource = history.data?.source || fund.source;

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Fund profile"
        title={fund.name || `${code} 基金详情`}
        description={`${fund.code} · ${fund.fund_type || "类型未知"} · ${fund.primary_theme || "主题未知"}。浏览结构化字段与本地历史净值，不构成推荐。`}
        actions={
          <Link className="back-link" to={returnTo} aria-label="返回基金终端">
            <ArrowLeft size={17} aria-hidden /> 返回基金终端
          </Link>
        }
      />

      <section className="fund-detail-identity" aria-label="基金身份与质量">
        <div>
          <span className="fund-detail-code">{fund.code}</span>
          <div className="tag-row">
            <StatusBadge tone={qualityTone(fund.data_quality_grade)}>{fund.stale ? "stale" : fund.data_quality_grade}</StatusBadge>
            {fund.exchange_traded ? <StatusBadge tone="info">ETF</StatusBadge> : null}
            {(fund.themes || []).map((theme) => <span className="tag" key={theme}>{theme}</span>)}
          </div>
        </div>
        <DataFreshnessStrip
          label="基金基础数据新鲜度"
          asOf={fund.as_of}
          updatedAt={fund.updated_at}
          expiresAt={fund.expires_at}
          source={fund.source}
          stale={fund.stale}
          dataQualityGrade={fund.data_quality_grade}
          compact
        />
      </section>

      <section className="metric-grid" aria-label="基金核心字段">
        <Metric label="单位净值" value={formatNumber(fund.nav, 4)} detail={fund.valuation_date || fund.as_of || "日期缺失"} />
        <Metric label="近 1 月" value={formatReturn(fund.returns["1m"])} detail="结构化全市场索引" />
        <Metric label="近 3 月" value={formatReturn(fund.returns["3m"])} detail="结构化全市场索引" />
        <Metric label="规模" value={formatNumber(fund.scale)} detail={fund.scale == null ? "字段缺失保留为空" : "全市场基础索引"} />
      </section>

      <section className="content-band" aria-labelledby="fund-history-title">
        <div className="fund-history-header">
          <div>
            <p className="eyebrow">NAV history</p>
            <h2 id="fund-history-title">历史净值</h2>
          </div>
          <div className="history-window-tabs" aria-label="历史净值时间范围">
            {HISTORY_WINDOWS.map((item) => (
              <button
                key={item.value}
                type="button"
                aria-label={item.label}
                aria-pressed={historyWindow === item.value}
                className={historyWindow === item.value ? "history-window history-window--active" : "history-window"}
                onClick={() => setHistoryWindow(item.value)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
        {history.loading ? <StatePanel kind="loading" title="正在读取历史净值" description="仅读取已有本地历史缓存和结构化 API。" /> : null}
        {history.error ? <StatePanel kind="error" title="历史净值暂不可用" description={history.error} /> : null}
        {history.data && history.data.points.length ? (
          <>
            <FundNavChart code={fund.code} points={history.data.points} />
            <div className="history-summary">
              <div><span>最新净值</span><strong>{formatNumber(latest?.unit_nav, 4)}</strong></div>
              <div><span>样本</span><strong>{history.data.point_count} 个净值点</strong></div>
              <div><span>来源</span><strong>{primarySource || "--"}</strong></div>
              <div><span>截至</span><strong>{history.data.as_of || latest?.date || "--"}</strong></div>
            </div>
            <DataFreshnessStrip
              label="历史净值数据新鲜度"
              asOf={history.data.as_of}
              updatedAt={history.data.updated_at}
              expiresAt={history.data.expires_at}
              source={history.data.source}
              stale={history.data.stale}
              fallbackUsed={history.data.fallback_used}
              dataQualityGrade={history.data.data_quality_grade}
              compact
            />
            {history.data.warnings.length ? <p className="history-warning">{history.data.warnings.map((warning) => warning.message).join(" · ")}</p> : null}
          </>
        ) : null}
      </section>

      <div className="split-grid">
        <section className="content-band" aria-labelledby="fund-attributes-title">
          <div className="section-heading"><div><p className="eyebrow">Research enrichment</p><h2 id="fund-attributes-title">基金补充字段</h2></div></div>
          <dl className="detail-list">
            <div><dt>基金公司</dt><dd>{research.fund_company || "--"}</dd></div>
            <div><dt>基金经理</dt><dd>{research.fund_manager || "--"}</dd></div>
            <div><dt>成立日期</dt><dd>{research.inception_date || "--"}</dd></div>
            <div><dt>评级</dt><dd>{research.rating ?? "--"}</dd></div>
            <div><dt>主题</dt><dd>{fund.themes.length ? fund.themes.join(" · ") : "未分类"}</dd></div>
            <div><dt>覆盖状态</dt><dd>{research.data_coverage?.status || "unknown"}</dd></div>
          </dl>
        </section>
        <section className="content-band" aria-labelledby="fund-data-notes-title">
          <div className="section-heading"><div><p className="eyebrow">Data notes</p><h2 id="fund-data-notes-title">数据说明</h2></div></div>
          {missingFields.length ? (
            <div className="notice">
              <CircleAlert size={18} aria-hidden />
              <div><strong>缺失字段不会形成正向信号</strong><p>{missingFields.join(" · ")}。需补充可靠来源并通过回归验证后，才可能进入实验候选层。</p></div>
            </div>
          ) : <p className="empty-copy">当前研究补充字段未报告缺失项；仍需结合来源和日期人工核对。</p>}
          <div className="boundary-band"><strong>研究观察边界</strong><p>该详情不修改主评分或主风险，也不构成买卖建议。</p></div>
        </section>
      </div>
    </div>
  );
}
