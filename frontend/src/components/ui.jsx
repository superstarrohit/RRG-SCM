// Shared presentational components + data hook.
import React from "react";
import Icon from "./icons.jsx";
import { HScrollSlider } from "./charts.jsx";

export function fmtNum(n, digits = 0) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

// App is deployed for an India-based operation: money is shown in ₹ (INR)
// with Indian digit grouping (lakh/crore), via the en-IN locale.
export function fmtMoney(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  });
}

export const fmtPct = (n, d = 1) =>
  n === null || n === undefined ? "—" : `${fmtNum(n, d)}%`;

// ₹ value shown in millions, e.g. ₹6,095.2 M — for the dashboard KPIs.
export function fmtMoneyM(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return "₹" + Number(n / 1e6).toLocaleString("en-IN", {
    minimumFractionDigits: 1, maximumFractionDigits: 1,
  }) + " M";
}

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
  // Material Planning's stock-health status, each pinned to its own fixed color.
  Excess: "b-status-amber", Safe: "b-status-green", Alarm: "b-status-yellow",
  Risk: "b-status-red", Stockout: "b-status-black",
};
// `value` picks the badge's color (a BADGE key); `label`, when given,
// overrides the displayed text — for callers that map an arbitrary value
// (e.g. a movement type) onto a shared tone rather than a status keyword.
export function Badge({ value, label }) {
  const text = label === undefined ? value : label;
  if (text === null || text === undefined || text === "")
    return <span className="muted">—</span>;
  return <span className={`badge ${BADGE[value] || "b-grey"}`}>{String(text).replace(/_/g, " ")}</span>;
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

// Parses an optional leading comparison operator off a numeric filter
// string (">100", "<=50", "20") so numeric columns can be range-filtered,
// not just matched by substring.
const NUM_FILTER = /^(>=|<=|>|<|=)?\s*(-?\d+(?:\.\d+)?)\s*$/;

// A DataTable with a click-to-sort header (per column, 3-state: asc / desc /
// off) and a per-column filter row (free-text substring for text columns —
// with optional >, >=, <, <=, = prefixes for numeric ones — or a dropdown
// when the column declares `filterType: "select"` + `options`). Filtering
// and sorting run client-side over whatever rows the server already
// returned, so it's a fast local refine on top of the global filters
// panel — built for wide, dense report tables (e.g. Material Planning)
// rather than replacing server-side filtering. Reuses the charts' own
// horizontal-scroll slider so a table with many columns stays as easy to
// pan across as a wide chart.
// localStorage-backed table layout: sort, per-column filters and any
// manually-resized column widths, so a table looks the way you left it next
// time you open the page instead of resetting every reload.
function loadTableLayout(storageKey) {
  try {
    return JSON.parse(localStorage.getItem(`table-layout:${storageKey}`) || "{}");
  } catch {
    return {};
  }
}
function saveTableLayout(storageKey, layout) {
  try {
    localStorage.setItem(`table-layout:${storageKey}`, JSON.stringify(layout));
  } catch { /* ignore (private browsing, storage full, ...) */ }
}

export function SortableTable({ columns, rows, storageKey = "default" }) {
  const safeRows = rows || [];
  const initial = React.useMemo(() => loadTableLayout(storageKey), [storageKey]);
  const [sort, setSort] = React.useState(initial.sort || { key: null, dir: 1 });
  const [filters, setFilters] = React.useState(initial.filters || {});
  // Empty until the user drags a column border for the first time — see
  // beginResize, which then snapshots every column's current rendered width
  // so the rest of the table doesn't jump when it switches to a fixed
  // layout. Restored from localStorage if this table was resized before.
  const [colWidths, setColWidths] = React.useState(initial.colWidths || {});
  React.useEffect(() => {
    saveTableLayout(storageKey, { sort, filters, colWidths });
  }, [storageKey, sort, filters, colWidths]);

  const wrapRef = React.useRef(null);
  const headRowRef = React.useRef(null);
  const hasCustomWidths = Object.keys(colWidths).length > 0;

  // Drag-to-resize a column border. The first resize of this table snapshots
  // every column's current auto-computed width so switching to a fixed
  // table-layout (needed for the width to stick and for cell text to wrap
  // instead of forcing the column wider) doesn't visibly reflow the table.
  const beginResize = (colKey, e) => {
    e.preventDefault();
    e.stopPropagation(); // don't also trigger the header's sort click
    let widths = colWidths;
    if (!hasCustomWidths && headRowRef.current) {
      widths = {};
      const cells = headRowRef.current.children;
      columns.forEach((c, i) => {
        widths[c.key] = Math.round(cells[i]?.getBoundingClientRect().width || 120);
      });
      setColWidths(widths);
    }
    const startWidth = widths[colKey] || 120;
    const startX = e.clientX;
    const onMove = (ev) => {
      const next = Math.max(60, Math.round(startWidth + (ev.clientX - startX)));
      setColWidths((prev) => ({ ...prev, [colKey]: next }));
    };
    const onUp = () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  };
  // The filter row sticks right below the sort-header row, so it needs that
  // row's real rendered height as its own `top` offset — measured rather
  // than hardcoded, since row height depends on font size/theme/zoom.
  const [headRowH, setHeadRowH] = React.useState(0);
  React.useEffect(() => {
    const measure = () => setHeadRowH(headRowRef.current?.offsetHeight || 0);
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  // Ascending <-> descending only — a 3rd state that cleared the sort
  // entirely made repeated clicks snap the table back to its original,
  // unsorted order, which read as the sort "reverting" on its own.
  const toggleSort = (key) => {
    setSort((s) => (s.key === key && s.dir === 1 ? { key, dir: -1 } : { key, dir: 1 }));
  };
  const setFilter = (key, value) => setFilters((f) => ({ ...f, [key]: value }));
  const activeFilters = Object.entries(filters).filter(([, v]) => v);

  const filtered = React.useMemo(() => {
    if (!activeFilters.length) return safeRows;
    return safeRows.filter((r) =>
      activeFilters.every(([key, val]) => {
        const col = columns.find((c) => c.key === key);
        const raw = r[key];
        if (col?.filterType === "select") return String(raw ?? "") === val;
        if (col?.num) {
          const m = NUM_FILTER.exec(val);
          if (m) {
            if (raw == null) return false;
            const op = m[1] || "=", n = Number(m[2]), rv = Number(raw);
            if (op === ">=") return rv >= n;
            if (op === "<=") return rv <= n;
            if (op === ">") return rv > n;
            if (op === "<") return rv < n;
            return rv === n;
          }
        }
        return String(raw ?? "").toLowerCase().includes(val.trim().toLowerCase());
      })
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [safeRows, filters, columns]);

  const sorted = React.useMemo(() => {
    if (!sort.key) return filtered;
    const col = columns.find((c) => c.key === sort.key);
    const copy = [...filtered];
    copy.sort((a, b) => {
      const av = a[sort.key], bv = b[sort.key];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;   // nulls sort last regardless of direction
      if (bv == null) return -1;
      if (col?.num) return (av - bv) * sort.dir;
      return String(av).localeCompare(String(bv)) * sort.dir;
    });
    return copy;
  }, [filtered, sort, columns]);

  if (!safeRows.length) return <div className="empty">No rows.</div>;

  return (
    <div>
      <div className="table-toolbar">
        <span className="muted">{fmtNum(sorted.length)} of {fmtNum(safeRows.length)} rows</span>
        <span style={{ display: "flex", gap: 12 }}>
          {hasCustomWidths && (
            <button className="table-clear-filters" onClick={() => setColWidths({})}>
              Reset column widths
            </button>
          )}
          {activeFilters.length > 0 && (
            <button className="table-clear-filters" onClick={() => setFilters({})}>
              Clear {activeFilters.length} filter{activeFilters.length > 1 ? "s" : ""}
            </button>
          )}
        </span>
      </div>
      {/* Above the table, not below — with up to 1,000 rows the table can run
          tens of thousands of pixels tall, so a slider placed after it (like
          a chart's) would be practically unreachable. */}
      <HScrollSlider scrollRef={wrapRef} />
      <div className="table-wrap table-wrap-scroll" ref={wrapRef}>
        <table style={hasCustomWidths ? { tableLayout: "fixed" } : undefined}>
          {hasCustomWidths && (
            <colgroup>
              {columns.map((c) => (
                <col key={c.key} style={{ width: `${colWidths[c.key] || 120}px` }} />
              ))}
            </colgroup>
          )}
          <thead>
            <tr ref={headRowRef}>
              {columns.map((c) => (
                <th key={c.key} className={`sortable ${c.num ? "num" : ""}`} onClick={() => toggleSort(c.key)}>
                  {c.label}
                  <span className={`sort-ind${sort.key === c.key ? " active" : ""}`}>
                    {sort.key === c.key ? (sort.dir === 1 ? "▲" : "▼") : "↕"}
                  </span>
                  <span
                    className="col-resizer"
                    onMouseDown={(e) => beginResize(c.key, e)}
                    onClick={(e) => e.stopPropagation()}
                    title="Drag to resize column"
                  />
                </th>
              ))}
            </tr>
            <tr className="filter-row" style={{ "--filter-row-top": `${headRowH}px` }}>
              {columns.map((c) => (
                <th key={c.key} className={c.num ? "num" : ""} onClick={(e) => e.stopPropagation()}>
                  {c.filterType === "select" ? (
                    <select value={filters[c.key] || ""} onChange={(e) => setFilter(c.key, e.target.value)}>
                      <option value="">All</option>
                      {(c.options || []).map((o) => <option key={o} value={o}>{o}</option>)}
                    </select>
                  ) : (
                    <input
                      type="text"
                      placeholder={c.num ? "e.g. >100" : "Filter…"}
                      value={filters[c.key] || ""}
                      onChange={(e) => setFilter(c.key, e.target.value)}
                    />
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!sorted.length ? (
              <tr><td colSpan={columns.length} className="empty">No rows match these filters.</td></tr>
            ) : sorted.map((r, i) => (
              <tr key={i}>
                {columns.map((c) => (
                  <td key={c.key} className={`${c.num ? "num" : ""}${hasCustomWidths ? " wrap" : ""}`}>
                    {c.render ? c.render(r[c.key], r) : (r[c.key] ?? "—")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
