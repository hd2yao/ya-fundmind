import { Menu, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { StatusBadge } from "../components/StatusBadge";
import { NAVIGATION_ITEMS } from "../lib/routes";

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        跳到主要内容
      </a>
      <aside className="sidebar" data-mobile-open={String(mobileOpen)}>
        <div className="brand-row">
          <div className="brand-mark" aria-hidden>
            YA
          </div>
          <div className="brand-copy">
            <strong>FundMind OS</strong>
            <span>Research Console</span>
          </div>
          <button className="icon-button sidebar-close" type="button" aria-label="关闭导航" onClick={() => setMobileOpen(false)}>
            <X size={20} aria-hidden />
          </button>
        </div>

        <nav className="primary-nav" aria-label="主要导航" data-mobile-open={String(mobileOpen)}>
          {NAVIGATION_ITEMS.map(({ path, label, description, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              end={path === "/"}
              aria-label={label}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) => `nav-item${isActive ? " nav-item--active" : ""}`}
            >
              <Icon size={20} strokeWidth={1.8} aria-hidden />
              <span>
                <strong>{label}</strong>
                <small>{description}</small>
              </span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-boundary">
          <ShieldCheck size={18} aria-hidden />
          <div>
            <strong>仅用于研究观察与人工审核</strong>
            <span>不自动交易，不接券商，不构成买卖建议。</span>
          </div>
        </div>
      </aside>

      {mobileOpen ? (
        <button className="nav-scrim" type="button" aria-label="关闭导航遮罩" onClick={() => setMobileOpen(false)} />
      ) : null}

      <div className="workspace">
        <header className="topbar">
          <button className="icon-button menu-button" type="button" aria-label="打开导航" onClick={() => setMobileOpen(true)}>
            <Menu size={21} aria-hidden />
          </button>
          <div className="topbar-title">
            <span>YA FundMind OS</span>
            <small>本地基金与 ETF 投研工作台</small>
          </div>
          <div className="topbar-status" aria-label="应用状态">
            <StatusBadge tone="success">本地运行</StatusBadge>
            <StatusBadge tone="info">研究模式</StatusBadge>
          </div>
        </header>
        <main id="main-content" className="main-content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
