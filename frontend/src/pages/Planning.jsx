import React from "react";
import { api } from "../api/client.js";
import {
  Panel, PageHeader, SortableTable, Badge,
  Loading, ErrorState, EmptyState, useApi, fmtNum,
} from "../components/ui.jsx";
import { useFilters } from "../components/filters.jsx";

const STATUS_OPTIONS = ["Stockout", "Risk", "Alarm", "Safe", "Excess"];

// Any negative figure in this report (a shortfall, a net outflow of
// receipts for the month, ...) is worth flagging the same way regardless
// of which column it's in.
const numCell = (v) => (
  <span style={{ color: v < 0 ? "var(--red)" : "inherit" }}>{fmtNum(v)}</span>
);

// Forecast is the net requirement to procure that month to still hold
// safety stock — a positive value means action is needed, so flag it in
// red rather than the usual neutral number color (it's clipped at 0, so
// never negative — no conflict with numCell's rule).
const forecastCell = (v) => (
  <span style={{ color: v > 0 ? "var(--red)" : "inherit" }}>{fmtNum(v)}</span>
);

const planCols = [
  { key: "material_code", label: "Material", render: (v) => <span className="mono strong">{v}</span> },
  { key: "description", label: "Material Description" },
  { key: "vendor", label: "Vendor" },
  { key: "m1_demand", label: "Demand (M1)", num: true, render: numCell },
  { key: "safety_stock", label: "Safety Stock", num: true, render: numCell },
  { key: "current_stock", label: "Current Stock", num: true, render: numCell },
  { key: "warehouse_stock", label: "Warehouse Stock", num: true, render: numCell },
  { key: "receipts", label: "Receipts", num: true, render: numCell },
  { key: "reach_days", label: "Reach (Days)", num: true, render: (v) => v == null ? "—" : numCell(v) },
  {
    key: "status", label: "Material Status", filterType: "select", options: STATUS_OPTIONS,
    render: (v) => <Badge value={v} />,
  },
  { key: "open_po", label: "Open PO", num: true, render: numCell },
  { key: "m1_forecast", label: "M1 Forecast", num: true, render: forecastCell },
  { key: "m1_bal", label: "M1 Bal", num: true, render: numCell },
  { key: "m2_demand", label: "M2 Demand", num: true, render: numCell },
  { key: "m2_forecast", label: "M2 Forecast", num: true, render: forecastCell },
  { key: "m2_bal", label: "M2 Bal", num: true, render: numCell },
  { key: "m3_demand", label: "M3 Demand", num: true, render: numCell },
  { key: "m3_forecast", label: "M3 Forecast", num: true, render: forecastCell },
  { key: "m3_bal", label: "M3 Bal", num: true, render: numCell },
  { key: "m4_demand", label: "M4 Demand", num: true, render: numCell },
  { key: "m4_forecast", label: "M4 Forecast", num: true, render: forecastCell },
  { key: "m4_bal", label: "M4 Bal", num: true, render: numCell },
];

// Stock (and everything derived from it — status, reach days, receipts, the
// M1-M4 rollup) is normally as of the latest upload. This page-specific date
// pins it to an earlier point instead — separate from the global Date Range
// filter, which scopes *demand history* elsewhere but has no stock of its
// own to scope here.
function StockDateFilter({ value, onChange }) {
  return (
    <span className="fp-date" style={{ background: "var(--surface)" }}>
      <span className="fp-date-tag">Stock</span>
      <input type="date" aria-label="Stock as of" value={value} onChange={(e) => onChange(e.target.value)} />
      {value && (
        <button className="fp-combo-clear" title="Use latest stock" aria-label="Use latest stock"
                onClick={() => onChange("")}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        </button>
      )}
    </span>
  );
}

const STOCK_DATE_KEY = "material-planning:stock-date";

export default function Planning() {
  const f = useFilters();
  const [stockDate, setStockDateState] = React.useState(
    () => { try { return localStorage.getItem(STOCK_DATE_KEY) || ""; } catch { return ""; } },
  );
  const setStockDate = (v) => {
    setStockDateState(v);
    try { v ? localStorage.setItem(STOCK_DATE_KEY, v) : localStorage.removeItem(STOCK_DATE_KEY); } catch { /* ignore */ }
  };
  const { loading, data, error } = useApi(
    () => api.planning({ ...f.params, stock_date: stockDate || undefined }),
    [f.key, stockDate],
  );
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const head = (
    <PageHeader
      title="Material Planning (MRP)"
      subtitle="Current stock vs safety / refill / max levels, and a rolling M1–M4 net-requirement (Forecast) and projected-balance (Bal) outlook."
      asOf={data.as_of}
      right={<StockDateFilter value={stockDate} onChange={setStockDate} />}
    />
  );
  if (data.empty) return <div>{head}<EmptyState message={data.message} /></div>;

  return (
    <div>
      {head}
      <Panel title="Material Plan">
        <SortableTable columns={planCols} rows={data.rows} storageKey="material-planning" />
      </Panel>
    </div>
  );
}
