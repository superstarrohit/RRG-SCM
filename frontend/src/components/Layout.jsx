import React from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import Icon from "./icons.jsx";
import { FiltersPanel } from "./filters.jsx";
import { ThemeCenterButton } from "./theme.jsx";

const TABS = [
  { to: "/", label: "Dashboard", icon: "dashboard", end: true },
  { to: "/incoming", label: "Incoming", icon: "truck" },
  { to: "/planning", label: "Material Planning", icon: "box" },
  { to: "/fg-planning", label: "FG Planning", icon: "factory" },
  { to: "/stock-monitoring", label: "Stock", icon: "gauge" },
  { to: "/inventory-monitoring", label: "Inventory", icon: "trend" },
  { to: "/vendor-receipts", label: "Receipts", icon: "receipt" },
  { to: "/movements", label: "Movements", icon: "flow" },
  { to: "/forecasting", label: "Forecast", icon: "target" },
  { to: "/data", label: "Data", icon: "database" },
];

export default function Layout({ children }) {
  const navigate = useNavigate();
  const location = useLocation();
  const tabsRef = React.useRef(null);

  // Keep the active tab scrolled into view on route change (narrow screens).
  React.useEffect(() => {
    const active = tabsRef.current?.querySelector(".tab.active");
    active?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }, [location.pathname]);

  // Let a plain vertical mouse-wheel scroll the tab strip horizontally —
  // there are more tabs than fit on most screens, so this makes the whole
  // row reachable without a dedicated horizontal scrollbar. React's onWheel
  // is passive (preventDefault is a no-op there), so this needs a real
  // addEventListener with passive:false to stop the page scrolling too.
  React.useEffect(() => {
    const el = tabsRef.current;
    if (!el) return;
    const onWheel = (e) => {
      if (el.scrollWidth <= el.clientWidth) return;
      if (Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
      el.scrollLeft += e.deltaY;
      e.preventDefault();
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  return (
    <div className="app">
      <div style={{ background: "#ffe600", color: "#000", textAlign: "center", fontWeight: 800, fontSize: 14, padding: "6px 0", letterSpacing: 1 }}>
        DEBUG MARKER — LIVE BUILD CHECK — if you can read this, your preview is reaching the latest code
      </div>
      <header className="topbar">
        <div className="brand">
          <div className="mark"><Icon name="cube" /></div>
          <div>
            <div className="title">RRG·SCM</div>
            <div className="sub">Supply Chain Analytics &amp; Planning</div>
          </div>
        </div>
        <div className="tabs-wrap">
          <nav className="tabs" ref={tabsRef}>
            {TABS.map((t) => (
              <NavLink
                key={t.to}
                to={t.to}
                end={t.end}
                className={({ isActive }) => "tab" + (isActive ? " active" : "")}
              >
                <Icon name={t.icon} />
                {t.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="actions">
          <ThemeCenterButton />
          <button className="btn ghost" onClick={() => window.location.reload()} title="Refresh">
            <Icon name="refresh" />
            <span className="btn-label">Refresh</span>
          </button>
          <button className="btn green" onClick={() => navigate("/data")} title="Upload a dump">
            <Icon name="upload" />
            <span className="btn-label">Upload</span>
          </button>
        </div>
      </header>
      <div className="body-shell">
        <main className="content">
          <div className="page-enter" key={location.pathname}>{children}</div>
        </main>
        <FiltersPanel />
      </div>
    </div>
  );
}
