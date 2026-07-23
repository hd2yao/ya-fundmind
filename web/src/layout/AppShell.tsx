import { Menu, Search, ShieldCheck, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { StatusBadge } from "../components/StatusBadge";
import { getNavigationItem, NAVIGATION_GROUPS } from "../lib/routes";

const NARROW_VIEWPORT_QUERY = "(max-width: 960px)";

function useNarrowViewport() {
  const [isNarrow, setIsNarrow] = useState(
    () => typeof window.matchMedia === "function" && window.matchMedia(NARROW_VIEWPORT_QUERY).matches
  );

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return undefined;
    const media = window.matchMedia(NARROW_VIEWPORT_QUERY);
    const update = () => setIsNarrow(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  return isNarrow;
}

export function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [globalQuery, setGlobalQuery] = useState("");
  const isNarrow = useNarrowViewport();
  const location = useLocation();
  const navigate = useNavigate();
  const currentWorkspace = getNavigationItem(location.pathname);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const navigationHidden = isNarrow && !mobileOpen;

  useEffect(() => {
    if (isNarrow && mobileOpen) closeButtonRef.current?.focus();
  }, [isNarrow, mobileOpen]);

  function closeMobileNavigation() {
    setMobileOpen(false);
    if (isNarrow) menuButtonRef.current?.focus();
  }

  function submitGlobalSearch(event: FormEvent) {
    event.preventDefault();
    const query = globalQuery.trim();
    navigate(query ? `/funds?q=${encodeURIComponent(query)}` : "/funds");
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        跳到主要内容
      </a>
      <aside
        className="sidebar"
        data-mobile-open={String(mobileOpen)}
        aria-hidden={navigationHidden || undefined}
        inert={navigationHidden || undefined}
      >
        <div className="brand-row">
          <div className="brand-mark" aria-hidden>
            YA
          </div>
          <div className="brand-copy">
            <strong>FundMind OS</strong>
            <span>本地基金数据终端</span>
          </div>
          <button ref={closeButtonRef} className="icon-button sidebar-close" type="button" aria-label="关闭导航" onClick={closeMobileNavigation}>
            <X size={20} aria-hidden />
          </button>
        </div>

        <nav className="primary-nav" aria-label="主要导航" data-mobile-open={String(mobileOpen)}>
          {NAVIGATION_GROUPS.map((group) => (
            <section className="nav-section" key={group.label} aria-label={group.label}>
              <p className="nav-section__label">{group.label}</p>
              {group.items.map(({ path, label, description, icon: Icon }) => (
                <NavLink
                  key={path}
                  to={path}
                  aria-label={label}
                  onClick={closeMobileNavigation}
                  className={({ isActive }) => `nav-item${isActive ? " nav-item--active" : ""}`}
                >
                  <Icon size={19} strokeWidth={1.8} aria-hidden />
                  <span>
                    <strong>{label}</strong>
                    <small>{description}</small>
                  </span>
                </NavLink>
              ))}
            </section>
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
        <button className="nav-scrim" type="button" aria-label="关闭导航遮罩" onClick={closeMobileNavigation} />
      ) : null}

      <div className="workspace">
        <header className="topbar">
          <button ref={menuButtonRef} className="icon-button menu-button" type="button" aria-label="打开导航" onClick={() => setMobileOpen(true)}>
            <Menu size={21} aria-hidden />
          </button>
          <div className="topbar-title">
            <span>当前工作区 · {currentWorkspace.label}</span>
            <small>{currentWorkspace.description}</small>
          </div>
          <form className="global-fund-search" role="search" onSubmit={submitGlobalSearch}>
            <Search size={17} aria-hidden />
            <input
              type="search"
              aria-label="全局搜索基金"
              placeholder="搜索基金代码或名称"
              value={globalQuery}
              onChange={(event) => setGlobalQuery(event.target.value)}
            />
            <button type="submit" aria-label="提交全局基金搜索" title="搜索基金">
              <Search size={16} aria-hidden />
            </button>
          </form>
          <div className="topbar-status" aria-label="应用状态">
            <StatusBadge tone="success">本地运行</StatusBadge>
            <StatusBadge tone="info">只读研究</StatusBadge>
          </div>
        </header>
        <main id="main-content" className="main-content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
