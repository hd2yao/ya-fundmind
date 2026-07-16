import { Link, Route, Routes } from "react-router-dom";

function Overview() {
  return (
    <main>
      <p>YA FundMind OS · 本地基金与 ETF 投研工作台</p>
      <h1>研究总览</h1>
      <p>读取本地结构化研究数据，用于观察与人工审核。</p>
      <p>不自动交易，不接券商，不构成买卖建议或收益承诺。</p>
    </main>
  );
}

function NotFound() {
  return (
    <main>
      <h1>页面不存在</h1>
      <p>该本地研究页面不存在，或地址已经变更。</p>
      <Link to="/">返回研究总览</Link>
    </main>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Overview />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
