import { Link, Route, Routes } from "react-router-dom";

import { AppShell } from "./layout/AppShell";

function PageIntro({ title, description }: { title: string; description: string }) {
  return (
    <section className="page-section" aria-labelledby="page-title">
      <div className="page-heading">
        <p className="eyebrow">Research workspace</p>
        <h1 id="page-title">{title}</h1>
        <p>{description}</p>
      </div>
    </section>
  );
}

function Overview() {
  return <PageIntro title="研究总览" description="查看最新运行、数据质量、待复核事项和研究摘要。" />;
}

function Placeholder({ title, description }: { title: string; description: string }) {
  return <PageIntro title={title} description={description} />;
}

function NotFound() {
  return (
    <section className="page-section not-found" aria-labelledby="not-found-title">
      <p className="eyebrow">404</p>
      <h1 id="not-found-title">页面不存在</h1>
      <p>该本地研究页面不存在，或地址已经变更。</p>
      <Link className="text-link" to="/">
        返回研究总览
      </Link>
    </section>
  );
}

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Overview />} />
        <Route path="/market" element={<Placeholder title="市场情报" description="观察市场主题、趋势变化与关联证据。" />} />
        <Route path="/funds" element={<Placeholder title="自选研究" description="研究 watchlist 中的基金与 ETF，不代表全市场推荐。" />} />
        <Route path="/portfolio" element={<Placeholder title="组合分析" description="查看持仓暴露、集中度和数据缺口。" />} />
        <Route path="/news" element={<Placeholder title="新闻证据" description="浏览新闻与公告证据，并核对来源和时间。" />} />
        <Route path="/copilot" element={<Placeholder title="研究助手" description="基于本地结构化证据回答研究问题。" />} />
        <Route path="/review" element={<Placeholder title="人工审核" description="记录候选信号和证据的人工复核状态。" />} />
        <Route path="/reports" element={<Placeholder title="报告中心" description="浏览已生成的本地研究报告与运行产物。" />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
