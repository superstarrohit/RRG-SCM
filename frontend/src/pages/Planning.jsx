import React from "react";
import { api } from "../api/client.js";
import {
  Panel, PageHeader, DataTable, Badge,
  Loading, ErrorState, EmptyState, useApi, fmtNum,
} from "../components/ui.jsx";
import { useFilters } from "../components/filters.jsx";

// Maps our five stock-health statuses onto the shared Badge color palette
// (see StockMonitoring.jsx's STATUS_BADGE for the same convention).
const STATUS_BADGE = { Stockout: "short", Risk: "short", Alarm: "due_this_month", Safe: "ok", Excess: "excess" };

const planCols = [
  { key: "material_code", label: "Material", render: (v) => <span className="mono strong">{v}</span> },
  { key: "description", label: "Material Description" },
  { key: "m1_demand", label: "Demand (M1)", num: true, render: (v) => fmtNum(v) },
  { key: "safety_stock", label: "Safety Stock", num: true, render: (v) => fmtNum(v) },
  { key: "current_stock", label: "Current Stock", num: true, render: (v) => fmtNum(v) },
  { key: "warehouse_stock", label: "Warehouse Stock", num: true, render: (v) => fmtNum(v) },
  { key: "reach_days", label: "Reach (Days)", num: true, render: (v) => v == null ? "—" : fmtNum(v, 1) },
  { key: "status", label: "Material Status", render: (v) => <Badge value={STATUS_BADGE[v]} label={v} /> },
  { key: "open_po", label: "Open PO", num: true, render: (v) => fmtNum(v) },
  { key: "m1_shortage", label: "Shortage (M1)", num: true, render: (v) => fmtNum(v) },
  { key: "m2_demand", label: "M2 Requirement", num: true, render: (v) => fmtNum(v) },
  { key: "m2_shortage", label: "M2 Shortage", num: true, render: (v) => fmtNum(v) },
  { key: "m3_demand", label: "M3 Requirement", num: true, render: (v) => fmtNum(v) },
  { key: "m3_shortage", label: "M3 Shortage", num: true, render: (v) => fmtNum(v) },
  { key: "m4_demand", label: "M4 Requirement", num: true, render: (v) => fmtNum(v) },
  { key: "m4_shortage", label: "M4 Shortage", num: true, render: (v) => fmtNum(v) },
];

export default function Planning() {
  const f = useFilters();
  const { loading, data, error } = useApi(() => api.planning(f.params), [f.key]);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const head = (
    <PageHeader
      title="Material Planning (MRP)"
      subtitle="Current stock vs safety / refill / max levels, this month's demand and shortage, and the M2–M4 requirement outlook."
      asOf={data.as_of}
    />
  );
  if (data.empty) return <div>{head}<EmptyState message={data.message} /></div>;

  return (
    <div>
      {head}
      <Panel title={`Material Plan — ${fmtNum(data.rows.length)} materials`}>
        <DataTable columns={planCols} rows={data.rows} />
      </Panel>
    </div>
  );
}
