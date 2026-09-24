import React from "react";
import { api } from "../api/client.js";
import {
  Panel, PageHeader, SortableTable, Badge,
  Loading, ErrorState, EmptyState, useApi, fmtNum,
} from "../components/ui.jsx";
import { useFilters } from "../components/filters.jsx";

const STATUS_OPTIONS = ["Stockout", "Risk", "Alarm", "Safe", "Excess"];

// A negative forecast means that month is projected to run out of stock —
// flag it in red so it reads at a glance, same convention as Costing's
// cost-variance column.
const forecastCell = (v) => (
  <span style={{ color: v < 0 ? "var(--red)" : "inherit" }}>{fmtNum(v)}</span>
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
  { key: "m1_forecast", label: "Forecast Stock (M1)", num: true, render: forecastCell },
  { key: "m2_demand", label: "M2 Requirement", num: true, render: (v) => fmtNum(v) },
  { key: "m2_forecast", label: "M2 Forecast Stock", num: true, render: forecastCell },
  { key: "m3_demand", label: "M3 Requirement", num: true, render: (v) => fmtNum(v) },
  { key: "m3_forecast", label: "M3 Forecast Stock", num: true, render: forecastCell },
  { key: "m4_demand", label: "M4 Requirement", num: true, render: (v) => fmtNum(v) },
  { key: "m4_forecast", label: "M4 Forecast Stock", num: true, render: forecastCell },
];

export default function Planning() {
  const f = useFilters();
  const { loading, data, error } = useApi(() => api.planning(f.params), [f.key]);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const head = (
    <PageHeader
      title="Material Planning (MRP)"
      subtitle="Current stock vs safety / refill / max levels, this month's demand, and the M2–M4 requirement and forecast-stock outlook."
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
