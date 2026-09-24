import React from "react";
import { api } from "../api/client.js";
import {
  Panel, PageHeader, SortableTable, Badge,
  Loading, ErrorState, EmptyState, useApi, fmtNum,
} from "../components/ui.jsx";
import { useFilters } from "../components/filters.jsx";

const STATUS_OPTIONS = ["Stockout", "Risk", "Alarm", "Safe", "Excess"];

// Forecast is the net requirement to procure that month to still hold
// safety stock — a positive value means action is needed, so flag it in
// red rather than the usual neutral number color.
const forecastCell = (v) => (
  <span style={{ color: v > 0 ? "var(--red)" : "inherit" }}>{fmtNum(v)}</span>
);

const planCols = [
  { key: "material_code", label: "Material", render: (v) => <span className="mono strong">{v}</span> },
  { key: "description", label: "Material Description" },
  { key: "m1_demand", label: "Demand (M1)", num: true, render: (v) => fmtNum(v) },
  { key: "safety_stock", label: "Safety Stock", num: true, render: (v) => fmtNum(v) },
  { key: "current_stock", label: "Current Stock", num: true, render: (v) => fmtNum(v) },
  { key: "warehouse_stock", label: "Warehouse Stock", num: true, render: (v) => fmtNum(v) },
  { key: "reach_days", label: "Reach (Days)", num: true, render: (v) => v == null ? "—" : fmtNum(v, 1) },
  {
    key: "status", label: "Material Status", filterType: "select", options: STATUS_OPTIONS,
    render: (v) => <Badge value={v} />,
  },
  { key: "open_po", label: "Open PO", num: true, render: (v) => fmtNum(v) },
  { key: "m1_forecast", label: "M1 Forecast", num: true, render: forecastCell },
  { key: "m1_bal", label: "M1 Bal", num: true, render: (v) => fmtNum(v) },
  { key: "m2_demand", label: "M2 Demand", num: true, render: (v) => fmtNum(v) },
  { key: "m2_forecast", label: "M2 Forecast", num: true, render: forecastCell },
  { key: "m2_bal", label: "M2 Bal", num: true, render: (v) => fmtNum(v) },
  { key: "m3_demand", label: "M3 Demand", num: true, render: (v) => fmtNum(v) },
  { key: "m3_forecast", label: "M3 Forecast", num: true, render: forecastCell },
  { key: "m3_bal", label: "M3 Bal", num: true, render: (v) => fmtNum(v) },
  { key: "m4_demand", label: "M4 Demand", num: true, render: (v) => fmtNum(v) },
  { key: "m4_forecast", label: "M4 Forecast", num: true, render: forecastCell },
  { key: "m4_bal", label: "M4 Bal", num: true, render: (v) => fmtNum(v) },
];

export default function Planning() {
  const f = useFilters();
  const { loading, data, error } = useApi(() => api.planning(f.params), [f.key]);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const head = (
    <PageHeader
      title="Material Planning (MRP)"
      subtitle="Current stock vs safety / refill / max levels, and a rolling M1–M4 net-requirement (Forecast) and projected-balance (Bal) outlook."
      asOf={data.as_of}
    />
  );
  if (data.empty) return <div>{head}<EmptyState message={data.message} /></div>;

  return (
    <div>
      {head}
      <Panel title="Material Plan">
        <SortableTable columns={planCols} rows={data.rows} />
      </Panel>
    </div>
  );
}
