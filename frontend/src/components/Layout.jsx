import React from "react";
import { NavLink } from "react-router-dom";

const NAV = [
  { section: "Overview" },
  { to: "/", label: "Dashboard", icon: "▦", end: true },
  { section: "Analytics" },
  { to: "/incoming", label: "Incoming Materials", icon: "🚚" },
  { to: "/planning", label: "Material Planning", icon: "📦" },
  { to: "/sourcing", label: "Sourcing", icon: "🤝" },
  { to: "/costing", label: "Costing", icon: "💲" },
  { to: "/fg-planning", label: "FG Planning", icon: "🏭" },
  { section: "Data" },
  { to: "/ingest", label: "Data Ingestion", icon: "⬆" },
];

export default function Layout({ children }) {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">RRG-SCM</div>
        <div className="tagline">Supply Chain Analytics</div>
        {NAV.map((item, i) =>
          item.section ? (
            <div className="nav-section" key={i}>
              {item.section}
            </div>
          ) : (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => "nav-item" + (isActive ? " active" : "")}
            >
              <span className="icon">{item.icon}</span>
              {item.label}
            </NavLink>
          )
        )}
        <div className="spacer" />
        <div className="tagline" style={{ paddingTop: 12 }}>
          v0.1 · analytics · planning · sourcing · costing · FG
        </div>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}
