import React from "react";
import { api } from "../api/client.js";
import {
  KpiCard,
  Panel,
  DataTable,
  Badge,
  Loading,
  ErrorState,
  EmptyState,
  useApi,
  fmtMoney,
  fmtNum,
} from "../components/ui.jsx";

const planCols = [
  { key: "material_code", label: "Material" },
  { key: "description", label: "Description" },
  { key: "on_hand", label: "On Hand", num: true, render: (v) => fmtNum(v) },
  { key: "incoming", label: "Incoming", num: true, render: (v) => fmtNum(v) },
  { key: "demand", label: "Demand", num: true, render: (v) => fmtNum(v) },
  { key: "safety_stock", label: "Safety", num: true, render: (v) => fmtNum(v) },
  { key: "net_requirement", label: "Net Req", num: true, render: (v) => fmtNum(v) },
  { key: "coverage_days", label: "Cover (d)", num: true, render: (v) => (v === null ? "—" : fmtNum(v, 1)) },
  { key: "suggested_order", label: "Suggest Order", num: true, render: (v) => fmtNum(v) },
  { key: "order_value", label: "Order Value", num: true, render: fmtMoney },
  { key: "status", label: "Status", render: (v) => <Badge value={v} /> },
];

export default function Planning() {
  const { loading, data, error } = useApi(() => api.planning({ top_n: 25 }), []);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const header = (
    <div className="page-header">
      <div>
        <h1>Material Planning (MRP)</h1>
        <p>Net requirements, shortages, excess and reorder alerts{data.as_of ? ` · as of ${data.as_of}` : ""}</p>
      </div>
    </div>
  );

  if (data.empty)
    return (
      <div>
        {header}
        <EmptyState message={data.message} />
      </div>
    );

  const k = data.kpis;
  return (
    <div>
      {header}
      <div className="kpi-grid">
        <KpiCard label="Materials Planned" value={fmtNum(k.materials_planned)} />
        <KpiCard label="Shortage Items" value={fmtNum(k.shortage_items)} accent={k.shortage_items ? "red" : "green"} />
        <KpiCard label="Excess Items" value={fmtNum(k.excess_items)} accent={k.excess_items ? "amber" : "green"} />
        <KpiCard label="Total Shortage Qty" value={fmtNum(k.total_shortage_qty)} />
        <KpiCard label="Suggested Order Value" value={fmtMoney(k.suggested_order_value)} />
        <KpiCard label="At/Below Reorder Point" value={fmtNum(k.at_or_below_rop)} accent={k.at_or_below_rop ? "amber" : "green"} />
      </div>

      <Panel title="🔴 Shortages — Recommended Purchases">
        <DataTable columns={planCols} rows={data.shortages} />
      </Panel>
      <Panel title="🟡 Reorder Point Alerts">
        <DataTable columns={planCols} rows={data.reorder_alerts} />
      </Panel>
      <Panel title="🟢 Excess / Slow-Moving">
        <DataTable columns={planCols} rows={data.excess} />
      </Panel>
    </div>
  );
}
