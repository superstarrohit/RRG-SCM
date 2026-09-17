// Shared presentational components + data hook.
import React from "react";
import Icon from "./icons.jsx";

export function fmtNum(n, digits = 0) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function fmtMoney(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

export const fmtPct = (n, d = 1) =>
  n === null || n === undefined ? "—" : `${fmtNum(n, d)}%`;

// KPI card with gradient icon chip + optional delta pill.
export function KpiCard({ label, value, sub, icon = "box", tone = "purple", delta }) {
  return (
    <div className="kpi">
      <div className="kpi-top">
        <div className={`icon-chip ${tone}`}>
          <Icon name={icon} />
        </div>
        {delta && (
          <span className={`delta ${delta.dir || "flat"}`}>
            {delta.dir === "up" ? "▲" : delta.dir === "down" ? "▼" : "—"} {delta.value}
          </span>
        )}
      </div>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}

const BADGE = {
  overdue: "b-red", short: "b-red", shortage: "b-red",
  due_this_week: "b-amber", due_this_month: "b-blue",
  future: "b-green", ok: "b-green", no_date: "b-grey", excess: "b-grey",
  A: "b-red", B: "b-amber", C: "b-green", vip: "b-vip",
};
export function Badge({ value }) {
  if (value === null || value === undefined || value === "")
    return <span className="muted">—</span>;
  return <span className={`badge ${BADGE[value] || "b-grey"}`}>{String(value).replace(/_/g, " ")}</span>;
}

export function Panel({ title, children, hint }) {
  return (
    <div className="panel">
      {title && (
        <h2>
          <span className="accent-bar" />
          {title}
          {hint && <span className="hint">{hint}</span>}
        </h2>
      )}
      {children}
    </div>
  );
}

export function DataTable({ columns, rows }) {
  if (!rows || !rows.length)
    return <div className="empty">No rows.</div>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.num ? "num" : ""}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c.key} className={c.num ? "num" : ""}>
                  {c.render ? c.render(r[c.key], r) : (r[c.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function PageHeader({ title, subtitle, asOf, right }) {
  return (
    <div className="page-header">
      <div>
        <h1><span className="accent-bar" />{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      <div className="controls">
        {right}
        {asOf && <span className="asof-chip">as of {asOf}</span>}
      </div>
    </div>
  );
}

// Premium skeleton loader: mirrors the page's usual shape (header, KPI row,
// panels) so the layout doesn't jump once data arrives.
export function Loading({ kpis = 6, panels = 2 }) {
  return (
    <div aria-busy="true" aria-label="Loading">
      <div className="skel skel-line" style={{ width: "38%", height: 22, marginBottom: 10 }} />
      <div className="skel skel-line" style={{ width: "58%", marginBottom: 22 }} />
      <div className="kpi-grid">
        {Array.from({ length: kpis }).map((_, i) => (
          <div className="skel skel-kpi" key={i} />
        ))}
      </div>
      <div className="panel-grid">
        {Array.from({ length: panels }).map((_, i) => (
          <div className="skel skel-panel" key={i} />
        ))}
      </div>
    </div>
  );
}

export function ErrorState({ error }) {
  return (
    <div className="alert error">
      Could not load data: {String(error?.message || error)}
      <div className="muted" style={{ marginTop: 6 }}>Is the backend running on :8000?</div>
    </div>
  );
}

export function EmptyState({ message }) {
  return (
    <div className="state">
      <div className="big">📭</div>
      <div>{message || "No data yet."}</div>
      <div className="muted" style={{ marginTop: 8 }}>
        Open <b>Data</b> to upload dumps, or run the seed script.
      </div>
    </div>
  );
}

export function useApi(fn, deps = []) {
  const [state, setState] = React.useState({ loading: true, data: null, error: null });
  React.useEffect(() => {
    let alive = true;
    setState({ loading: true, data: null, error: null });
    fn()
      .then((data) => alive && setState({ loading: false, data, error: null }))
      .catch((error) => alive && setState({ loading: false, data: null, error }));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}
