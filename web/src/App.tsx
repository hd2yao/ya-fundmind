import { Link, Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./layout/AppShell";
import { CopilotPage } from "./pages/CopilotPage";
import { MarketPage } from "./pages/MarketPage";
import { FundsPage } from "./pages/FundsPage";
import { FundDetailPage } from "./pages/FundDetailPage";
import { NewsPage } from "./pages/NewsPage";
import { OverviewPage } from "./pages/OverviewPage";
import { PortfolioPage } from "./pages/PortfolioPage";
import { ReportsPage } from "./pages/ReportsPage";
import { ReviewPage } from "./pages/ReviewPage";

function NotFound() {
  return (
    <section className="page-section not-found" aria-labelledby="not-found-title">
      <p className="eyebrow">404</p>
      <h1 id="not-found-title">页面不存在</h1>
      <p>该本地研究页面不存在，或地址已经变更。</p>
      <Link className="text-link" to="/market">
        返回行情总览
      </Link>
    </section>
  );
}

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Navigate to="/market" replace />} />
        <Route path="/market" element={<MarketPage />} />
        <Route path="/funds" element={<FundsPage />} />
        <Route path="/funds/:code" element={<FundDetailPage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/news" element={<NewsPage />} />
        <Route path="/copilot" element={<CopilotPage />} />
        <Route path="/review" element={<ReviewPage />} />
        <Route path="/status" element={<OverviewPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
