import React from "react";
import { api } from "../api/client.js";
import {
  KpiCard, Panel, PageHeader, DataTable, Badge,
  Loading, ErrorState, EmptyState, useApi, fmtMoney, fmtNum,
} from "../components/ui.jsx";
import { Donut, PALETTE } from "../components/charts.jsx";

const planCols = [
  { key: "material_code", label: "Material", render: (v) => <span className="mono strong">{v}</span> },
  { key: "description", label: "Description" },
  { key: "on_hand", label: "On Hand", num: true, render: (v) => fmtNum(v) },
  { key: "incoming", label: "Incoming", num: true, render: (v) => fmtNum(v) },
  { key: "demand", label: "Demand", num: true, render: (v) => fmtNum(v) },
  { key: "net_requirement", label: "Net Req", num: true, render: (v) => fmtNum(v) },
  { key: "coverage_days", label: "Cover (d)", num: true, render: (v) => v == null ? "—" : fmtNum(v, 1) },
  { key: "suggested_order", label: "Suggest Order", num: true, render: (v) => fmtNum(v) },
  { key: "order_value", label: "Order Value", num: true, render: fmtMoney },
  { key: "status", label: "Status", render: (v) => <Badge value={v} /> },
];

export default function Planning() {
  const { loading, data, error } = useApi(() => api.planning({ top_n: 25 }), []);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const head = (
    <PageHeader
      title="Material Planning (MRP)"
      subtitle="Net requirements, shortages, excess and reorder alerts with MOQ-aware suggested orders."
      asOf={data.as_of}
    />
  );
  if (data.empty) return <div>{head}<EmptyState message={data.message} /></div>;

  const k = data.kpis;
  const ok = Math.max(0, k.materials_planned - k.shortage_items - k.excess_items);
  const segs = [
    { label: "Shortage", value: k.shortage_items, color: PALETTE.red },
    { label: "Excess", value: k.excess_items, color: PALETTE.amber },
    { label: "Balanced", value: ok, color: PALETTE.green },
  ];

  return (
    <div>
      {head}
      <div className="kpi-grid">
        <KpiCard label="Materials Planned" value={fmtNum(k.materials_planned)} icon="box" tone="blue" />
        <KpiCard label="Shortage Items" value={fmtNum(k.shortage_items)} icon="alert" tone="red" />
        <KpiCard label="Excess Items" value={fmtNum(k.excess_items)} icon="layers" tone="amber" />
        <KpiCard label="Total Shortage Qty" value={fmtNum(k.total_shortage_qty)} icon="box" tone="purple" />
        <KpiCard label="Suggested Order Value" value={fmtMoney(k.suggested_order_value)} icon="dollar" tone="green" />
        <KpiCard label="At/Below Reorder Point" value={fmtNum(k.at_or_below_rop)} icon="clock" tone="amber" />
      </div>

      <div className="panel-grid">
        <Panel title="Planning Health">
          <Donut segments={segs} centerValue={fmtNum(k.materials_planned)} centerLabel="materials" />
        </Panel>
        <Panel title="🔴 Shortages — Recommended Purchases">
          <DataTable columns={planCols} rows={data.shortages} />
        </Panel>
      </div>

      <Panel title="🟡 Reorder Point Alerts">
        <DataTable columns={planCols} rows={data.reorder_alerts} />
      </Panel>
      <Panel title="🟢 Excess / Slow-Moving">
        <DataTable columns={planCols} rows={data.excess} />
      </Panel>
    </div>
  );
}
