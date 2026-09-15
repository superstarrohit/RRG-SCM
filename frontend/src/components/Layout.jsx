import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import Icon from "./icons.jsx";
import { FilterBar } from "./filters.jsx";

const TABS = [
  { to: "/", label: "Dashboard", icon: "dashboard", end: true },
  { to: "/incoming", label: "Incoming", icon: "truck" },
  { to: "/planning", label: "Planning", icon: "box" },
  { to: "/sourcing", label: "Sourcing", icon: "handshake" },
  { to: "/costing", label: "Costing", icon: "dollar" },
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
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="mark"><Icon name="cube" /></div>
          <div>
            <div className="title">RRG·SCM</div>
            <div className="sub">Supply Chain Analytics &amp; Planning</div>
          </div>
        </div>
        <nav className="tabs">
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
        <div className="actions">
          <button className="btn ghost" onClick={() => window.location.reload()}>
            <Icon name="refresh" /> Refresh
          </button>
          <button className="btn green" onClick={() => navigate("/ingest")}>
            <Icon name="upload" /> Upload Dump
          </button>
        </div>
      </header>
      <FilterBar />
      <main className="content">{children}</main>
    </div>
  );
}
