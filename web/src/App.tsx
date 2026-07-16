import { Link, Route, Routes } from "react-router-dom";

import { AppShell } from "./layout/AppShell";
import { MarketPage } from "./pages/MarketPage";
import { FundsPage } from "./pages/FundsPage";
import { NewsPage } from "./pages/NewsPage";
import { OverviewPage } from "./pages/OverviewPage";
import { PortfolioPage } from "./pages/PortfolioPage";

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
        <Route path="/" element={<OverviewPage />} />
        <Route path="/market" element={<MarketPage />} />
        <Route path="/funds" element={<FundsPage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/news" element={<NewsPage />} />
        <Route path="/copilot" element={<Placeholder title="研究助手" description="基于本地结构化证据回答研究问题。" />} />
        <Route path="/review" element={<Placeholder title="人工审核" description="记录候选信号和证据的人工复核状态。" />} />
        <Route path="/reports" element={<Placeholder title="报告中心" description="浏览已生成的本地研究报告与运行产物。" />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
