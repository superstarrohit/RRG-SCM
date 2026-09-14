// Small shared presentational components used across pages.
import React from "react";

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

export function KpiCard({ label, value, sub, accent }) {
  return (
    <div className={`kpi ${accent ? "accent-" + accent : ""}`}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}

export function Badge({ value }) {
  if (!value) return <span className="muted">—</span>;
  return <span className={`badge ${value}`}>{value.replace(/_/g, " ")}</span>;
}

export function Panel({ title, children, right }) {
  return (
    <div className="panel">
      {(title || right) && (
        <div style={{ display: "flex", alignItems: "center" }}>
          {title && <h2 style={{ flex: 1 }}>{title}</h2>}
          {right}
        </div>
      )}
      {children}
    </div>
  );
}

// Horizontal bar chart from [{label, value}].
export function BarChart({ data, valueFormat = fmtNum, color }) {
  const max = Math.max(1, ...data.map((d) => d.value || 0));
  if (!data.length) return <div className="muted">No data.</div>;
  return (
    <div>
      {data.map((d, i) => (
        <div className="bar-row" key={i}>
          <div className="bar-label" title={d.label}>
            {d.label}
          </div>
          <div className="bar-track">
            <div
              className="bar-fill"
              style={{
                width: `${((d.value || 0) / max) * 100}%`,
                background: color || undefined,
              }}
            />
          </div>
          <div className="bar-value">{valueFormat(d.value)}</div>
        </div>
      ))}
    </div>
  );
}

export function DataTable({ columns, rows }) {
  if (!rows || !rows.length) {
    return <div className="muted" style={{ padding: "12px 0" }}>No rows.</div>;
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.num ? "num" : ""}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c.key} className={c.num ? "num" : ""}>
                  {c.render ? c.render(r[c.key], r) : r[c.key] ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Loading() {
  return <div className="state">Loading…</div>;
}

export function ErrorState({ error }) {
  return (
    <div className="alert error">
      Could not load data: {String(error?.message || error)}
      <div className="muted" style={{ marginTop: 6 }}>
        Is the backend running on :8000?
      </div>
    </div>
  );
}

export function EmptyState({ message }) {
  return (
    <div className="state">
      <div className="big">📭</div>
      <div>{message || "No data yet."}</div>
      <div className="muted" style={{ marginTop: 8 }}>
        Go to <b>Data Ingestion</b> to upload dumps, or run the seed script.
      </div>
    </div>
  );
}

// Simple data-fetching hook.
export function useApi(fn, deps = []) {
  const [state, setState] = React.useState({ loading: true, data: null, error: null });
  React.useEffect(() => {
    let alive = true;
    setState({ loading: true, data: null, error: null });
    fn()
      .then((data) => alive && setState({ loading: false, data, error: null }))
      .catch((error) => alive && setState({ loading: false, data: null, error }));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}
