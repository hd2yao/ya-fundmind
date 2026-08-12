import { ArrowLeft, CircleAlert } from "lucide-react";
import { type KeyboardEvent, useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { getFundDetail, getFundHistory, getFundProfile } from "../api/client";
import type {
  FundHistoryWindow,
  ProductDataStatus,
  ProductFundDetailResponse,
  ProductFundHistoryResponse,
  ProductFundProfileResponse
} from "../api/types";
import { FundNavChart } from "../components/FundNavChart";
import { Metric } from "../components/Metric";
import { PageHeader } from "../components/PageHeader";
import { StatePanel } from "../components/StatePanel";
import { StatusBadge, type StatusTone } from "../components/StatusBadge";

type DetailState = { loading: boolean; data: ProductFundDetailResponse | null; error: string | null };
type HistoryState = { loading: boolean; data: ProductFundHistoryResponse | null; error: string | null };
type ProfileState = { loading: boolean; data: ProductFundProfileResponse | null; error: string | null };
type DetailTab = "overview" | "performance" | "fees";

const HISTORY_WINDOWS: Array<{ value: FundHistoryWindow; label: string }> = [
  { value: "1m", label: "1 月" },
  { value: "3m", label: "3 月" },
  { value: "6m", label: "6 月" },
  { value: "1y", label: "1 年" },
  { value: "all", label: "全部" }
];

const DETAIL_TABS: Array<{ value: DetailTab; label: string }> = [
  { value: "overview", label: "概览" },
  { value: "performance", label: "净值与业绩" },
  { value: "fees", label: "费率与规则" }
];

function formatReturn(value?: number | null) {
  if (value == null) return "--";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatNumber(value?: number | null, digits = 2) {
  if (value == null) return "--";
  return value.toLocaleString("zh-CN", { maximumFractionDigits: digits });
}

function formatScale(value?: number | null, unit?: string | null) {
  if (value == null) return "--";
  return `${formatNumber(value)}${unit || ""}`;
}

function dataStatusTone(status?: ProductDataStatus | null): StatusTone {
  if (status?.state === "updated") return "success";
  if (status?.state === "attention") return "warning";
  if (status?.state === "limited" || status?.state === "unavailable") return "critical";
  return "neutral";
}

function safeReturnTo(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return "/funds";
  const pathname = value.split("?", 1)[0];
  return ["/funds", "/watchlist", "/portfolio", "/news"].includes(pathname) ? value : "/funds";
}

export function FundDetailPage() {
  const { code = "" } = useParams();
  const location = useLocation();
  const validCode = /^\d{6}$/.test(code);
  const returnTo = safeReturnTo(new URLSearchParams(location.search).get("return_to"));
  const [activeTab, setActiveTab] = useState<DetailTab>("overview");
  const [detail, setDetail] = useState<DetailState>({ loading: true, data: null, error: null });
  const [profile, setProfile] = useState<ProfileState>({ loading: true, data: null, error: null });
  const [historyWindow, setHistoryWindow] = useState<FundHistoryWindow>("6m");
  const [history, setHistory] = useState<HistoryState>({ loading: false, data: null, error: null });

  useEffect(() => {
    setActiveTab("overview");
    setProfile({ loading: true, data: null, error: null });
    setHistoryWindow("6m");
    setHistory({ loading: false, data: null, error: null });
  }, [code]);

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
    if (!validCode || activeTab === "performance" || profile.data || profile.error) return undefined;
    const controller = new AbortController();
    setProfile((current) => ({ ...current, loading: true, error: null }));
    getFundProfile(code, controller.signal)
      .then((data) => setProfile({ loading: false, data, error: null }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setProfile({ loading: false, data: null, error: error instanceof Error ? error.message : "基金资料读取失败。" });
        }
      });
    return () => controller.abort();
  }, [activeTab, code, profile.data, profile.error, validCode]);

  useEffect(() => {
    if (!validCode || activeTab !== "performance") return undefined;
    const controller = new AbortController();
    setHistory((current) => ({ loading: true, data: current.data, error: null }));
    getFundHistory(code, historyWindow, controller.signal)
      .then((data) => setHistory({ loading: false, data, error: null }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setHistory({ loading: false, data: null, error: error instanceof Error ? error.message : "历史净值读取失败。" });
        }
      });
    return () => controller.abort();
  }, [activeTab, code, historyWindow, validCode]);

  if (!validCode) {
    return <StatePanel kind="error" title="基金代码无效" description="基金详情仅支持六位、已索引的基金代码。" />;
  }
  if (detail.loading) {
    return <StatePanel kind="loading" title="正在读取基金详情" description="读取基金索引与已有研究补充字段。" />;
  }
  if (detail.error || !detail.data) {
    return <StatePanel kind="error" title="基金详情暂不可用" description={detail.error || "当前索引未返回该基金。"} />;
  }

  const { fund, research } = detail.data;
  const latest = history.data?.points.at(-1);

  const selectTab = (tab: DetailTab) => setActiveTab(tab);
  const handleTabKey = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (![
      "ArrowLeft",
      "ArrowRight",
      "Home",
      "End"
    ].includes(event.key)) return;
    event.preventDefault();
    let nextIndex = index;
    if (event.key === "ArrowLeft") nextIndex = (index - 1 + DETAIL_TABS.length) % DETAIL_TABS.length;
    if (event.key === "ArrowRight") nextIndex = (index + 1) % DETAIL_TABS.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = DETAIL_TABS.length - 1;
    const nextTab = DETAIL_TABS[nextIndex].value;
    setActiveTab(nextTab);
    requestAnimationFrame(() => document.getElementById(`fund-tab-${nextTab}`)?.focus());
  };

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="基金资料"
        title={fund.name || `${code} 基金详情`}
        description={`${fund.code} · ${fund.fund_type || "类型未知"} · ${fund.primary_theme || "主题未知"}。浏览结构化字段与历史净值，不构成推荐。`}
        actions={
          <Link className="back-link" to={returnTo} aria-label="返回上一页">
            <ArrowLeft size={17} aria-hidden /> 返回上一页
          </Link>
        }
      />

      <section className="fund-detail-identity" aria-label="基金身份与数据状态">
        <div>
          <span className="fund-detail-code">{fund.code}</span>
          <div className="tag-row">
            <StatusBadge tone={dataStatusTone(fund.data_status)}>{fund.data_status.label}</StatusBadge>
            {fund.exchange_traded ? <StatusBadge tone="info">ETF</StatusBadge> : null}
            {(fund.themes || []).map((theme) => <span className="tag" key={theme}>{theme}</span>)}
          </div>
        </div>
        <div className="fund-detail-status">
          <span>数据日期</span>
          <strong>{fund.data_date || "--"}</strong>
          <p>{fund.data_status.description}</p>
        </div>
      </section>

      <section className="metric-grid" aria-label="基金核心字段">
        <Metric label="单位净值" value={formatNumber(fund.nav, 4)} detail={fund.data_date || "日期待补充"} />
        <Metric label="近 1 月" value={formatReturn(fund.returns["1m"])} detail="结构化全市场索引" />
        <Metric label="近 3 月" value={formatReturn(fund.returns["3m"])} detail="结构化全市场索引" />
        <Metric label="规模" value={formatNumber(fund.scale)} detail={fund.scale == null ? "字段缺失保留为空" : "全市场基础索引"} />
      </section>

      <div className="fund-profile-tabs" role="tablist" aria-label="基金详情栏目">
        {DETAIL_TABS.map((tab, index) => (
          <button
            key={tab.value}
            id={`fund-tab-${tab.value}`}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.value}
            aria-controls={`fund-panel-${tab.value}`}
            tabIndex={activeTab === tab.value ? 0 : -1}
            className={activeTab === tab.value ? "fund-profile-tab fund-profile-tab--active" : "fund-profile-tab"}
            onClick={() => selectTab(tab.value)}
            onKeyDown={(event) => handleTabKey(event, index)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "overview" ? (
        <section id="fund-panel-overview" className="fund-profile-panel" role="tabpanel" aria-labelledby="fund-tab-overview">
          <ProfileOverview profileState={profile} research={research} />
        </section>
      ) : null}

      {activeTab === "performance" ? (
        <section id="fund-panel-performance" className="fund-profile-panel" role="tabpanel" aria-labelledby="fund-tab-performance">
          <div className="fund-history-header">
            <div><p className="eyebrow">净值历史</p><h2>历史净值</h2></div>
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
          {history.loading ? <StatePanel kind="loading" title="正在读取历史净值" description="正在整理已有的结构化历史数据。" /> : null}
          {history.error ? <StatePanel kind="error" title="历史净值暂不可用" description={history.error} /> : null}
          {history.data && history.data.points.length ? (
            <>
              <FundNavChart code={fund.code || code} points={history.data.points} />
              <div className="history-summary">
                <div><span>最新净值</span><strong>{formatNumber(latest?.unit_nav, 4)}</strong></div>
                <div><span>样本</span><strong>{history.data.point_count} 个净值点</strong></div>
                <div><span>数据日期</span><strong>{history.data.data_date || latest?.date || "--"}</strong></div>
                <div><span>资料状态</span><strong>{history.data.data_status.label}</strong></div>
              </div>
              {history.data.data_status.state !== "updated" ? <p className="history-warning">{history.data.data_status.description}</p> : null}
            </>
          ) : null}
        </section>
      ) : null}

      {activeTab === "fees" ? (
        <section id="fund-panel-fees" className="fund-profile-panel" role="tabpanel" aria-labelledby="fund-tab-fees">
          <FeeAndRulePanel profileState={profile} />
        </section>
      ) : null}

      <div className="boundary-band"><strong>研究观察边界</strong><p>该详情不修改主评分或主风险，也不构成买卖建议。</p></div>
    </div>
  );
}

function ProfileOverview({
  profileState,
  research
}: {
  profileState: ProfileState;
  research: ProductFundDetailResponse["research"];
}) {
  if (profileState.loading) {
    return <StatePanel kind="loading" title="正在读取基金概况" description="正在整理基金公司、成立信息与规模资料。" />;
  }
  if (profileState.error || !profileState.data) {
    return <StatePanel kind="error" title="基金概况暂不可用" description={profileState.error || "当前没有可展示的基金概况。"} />;
  }
  const data = profileState.data;
  const overview = data.profile;
  const status = data.component_status.profile;
  const missingFields = research.missing_fields || [];
  return (
    <>
      <div className="profile-section-heading">
        <div><p className="eyebrow">产品概况</p><h2>基金概况</h2></div>
        <StatusBadge tone={dataStatusTone(status)}>{status.label}</StatusBadge>
      </div>
      <div className="split-grid">
        <section aria-label="基金概况字段">
          <dl className="detail-list detail-list--profile">
            <div><dt>基金全称</dt><dd>{overview?.full_name || data.fund.name || "--"}</dd></div>
            <div><dt>基金公司</dt><dd>{overview?.fund_company || research.fund_company || "--"}</dd></div>
            <div><dt>托管人</dt><dd>{overview?.custodian || "--"}</dd></div>
            <div><dt>基金经理</dt><dd>{overview?.fund_manager || research.fund_manager || "--"}</dd></div>
            <div><dt>成立日期</dt><dd>{overview?.inception_date || research.inception_date || "--"}</dd></div>
            <div><dt>发行日期</dt><dd>{overview?.issue_date || "--"}</dd></div>
            <div><dt>资产规模</dt><dd>{formatScale(overview?.asset_scale, overview?.asset_scale_unit)}</dd></div>
            <div><dt>份额规模</dt><dd>{formatScale(overview?.share_scale, overview?.share_scale_unit)}</dd></div>
            <div><dt>业绩基准</dt><dd>{overview?.benchmark || "--"}</dd></div>
            <div><dt>跟踪标的</dt><dd>{overview?.tracking_target || "--"}</dd></div>
          </dl>
        </section>
        <section className="profile-notes" aria-label="基金资料说明">
          <div className="fund-detail-status">
            <span>概况日期</span>
            <strong>{status.as_of || "--"}</strong>
            <p>{status.description}</p>
          </div>
          {missingFields.length ? (
            <div className="notice">
              <CircleAlert size={18} aria-hidden />
              <div><strong>缺失字段保持为空</strong><p>{missingFields.join(" · ")}。缺失资料不会形成正向信号。</p></div>
            </div>
          ) : <p className="empty-copy">当前概况没有额外缺失提示；仍请结合资料日期查看。</p>}
        </section>
      </div>
    </>
  );
}

function FeeAndRulePanel({ profileState }: { profileState: ProfileState }) {
  if (profileState.loading) {
    return <StatePanel kind="loading" title="正在读取费率与规则" description="正在整理申购、赎回与费率条件。" />;
  }
  if (profileState.error || !profileState.data) {
    return <StatePanel kind="error" title="费率与规则暂不可用" description={profileState.error || "当前没有可展示的费率资料。"} />;
  }
  const data = profileState.data;
  const rule = data.trading_rule;
  const ruleStatus = data.component_status.trading_rule;
  const feeStatus = data.component_status.fees;
  return (
    <>
      <div className="profile-section-heading">
        <div><p className="eyebrow">申赎信息</p><h2>交易规则</h2></div>
        <StatusBadge tone={dataStatusTone(ruleStatus)}>{ruleStatus.label}</StatusBadge>
      </div>
      {rule ? (
        <dl className="detail-list detail-list--rules">
          <div><dt>申购状态</dt><dd>{rule.purchase_status || "--"}</dd></div>
          <div><dt>赎回状态</dt><dd>{rule.redemption_status || "--"}</dd></div>
          <div><dt>下一开放日</dt><dd>{rule.next_open_date || "--"}</dd></div>
          <div><dt>起购金额</dt><dd>{rule.minimum_purchase_amount || "--"}</dd></div>
          <div><dt>日累计限额</dt><dd>{rule.daily_purchase_limit || "--"}</dd></div>
          <div><dt>确认规则</dt><dd>{rule.confirmation_rule || "--"}</dd></div>
        </dl>
      ) : <StatePanel kind="empty" title={ruleStatus.label} description={ruleStatus.description} />}

      <div className="profile-section-heading profile-section-heading--fees">
        <div><p className="eyebrow">费率条件</p><h2>费率明细</h2></div>
        <StatusBadge tone={dataStatusTone(feeStatus)}>{feeStatus.label}</StatusBadge>
      </div>
      {data.fees.length ? (
        <div className="table-wrap profile-fee-table">
          <table className="data-table">
            <thead><tr><th>费率类型</th><th>条件</th><th>期限</th><th>渠道</th><th>原费率</th><th>优惠费率</th></tr></thead>
            <tbody>
              {data.fees.map((fee, index) => (
                <tr key={`${fee.fee_type || "fee"}-${fee.condition || "all"}-${index}`}>
                  <td>{fee.fee_type || "--"}</td><td>{fee.condition || "--"}</td><td>{fee.period || "--"}</td>
                  <td>{fee.channel || "--"}</td><td>{fee.original_rate || "--"}</td><td>{fee.discounted_rate || "--"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <StatePanel kind="empty" title={feeStatus.label} description={feeStatus.description} />}
      <p className="history-warning">费率按来源原文展示；“每笔固定金额”等条件不会换算成百分比。</p>
    </>
  );
}
