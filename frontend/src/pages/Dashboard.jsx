import React from "react";
import { api } from "../api/client.js";
import {
  KpiCard, Panel, PageHeader, DataTable, Badge,
  Loading, ErrorState, useApi, fmtMoney, fmtNum, fmtPct,
} from "../components/ui.jsx";
import { Donut, VBars, LineChart, PALETTE } from "../components/charts.jsx";
import { useFilters } from "../components/filters.jsx";

const STATUS_COLOR = {
  Overdue: PALETTE.red,
  "Due this week": PALETTE.amber,
  "Due this month": PALETTE.blue,
  "Future (>30d)": PALETTE.green,
  "No ETA": PALETTE.grey,
};

export default function Dashboard() {
  const f = useFilters();
  const { loading, data, error } = useApi(() => api.overview(f.params), [f.key]);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const k = data.kpis;
  const statusSegs = data.incoming_status.map((s) => ({
    label: s.label, value: s.value, color: STATUS_COLOR[s.label] || PALETTE.purple,
  }));
  const supplierBars = data.top_suppliers.map((s) => ({
    label: (s.supplier_name || s.supplier_code || "").split(" ")[0], value: s.open_value,
  }));
  const arrivals = data.arrival_timeline.map((w) => ({
    label: w.label.length > 7 ? w.label.slice(5) : w.label, value: w.value,
  }));

  return (
    <div>
      <PageHeader
        title="Overall SCM Dashboard"
        subtitle="Executive summary across inventory, incoming, planning and sourcing."
        asOf={data.as_of}
      />

      <div className="kpi-grid">
        <KpiCard label="Inventory Value" value={fmtMoney(k.inventory_value)} icon="dollar" tone="green" />
        <KpiCard label="Incoming Value" value={fmtMoney(k.incoming_value)} icon="truck" tone="blue" />
        <KpiCard label="Overdue Incoming" value={fmtMoney(k.overdue_value)} icon="alert" tone="red"
          delta={{ value: `${fmtPct(k.overdue_value / (k.incoming_value || 1) * 100)} of value`, dir: "down" }} />
        <KpiCard label="Shortage Items" value={fmtNum(k.shortage_items)} icon="box" tone="amber" />
        <KpiCard label="Reorder Alerts" value={fmtNum(k.reorder_alerts)} icon="clock" tone="amber" />
        <KpiCard label="Active Suppliers" value={fmtNum(k.active_suppliers)} icon="handshake" tone="purple" />
        <KpiCard label="Single-Source Items" value={fmtNum(k.single_source_materials)} icon="alert" tone="amber" />
        <KpiCard label="Avg On-Time" value={fmtPct(k.avg_on_time_pct)} icon="chart" tone="cyan" />
      </div>

      <div className="panel-grid">
        <Panel title="Incoming Pipeline by Status">
          <Donut segments={statusSegs} centerValue={fmtMoney(k.incoming_value)} centerLabel="incoming" />
        </Panel>
        <Panel title="Top Suppliers by Committed Value">
          <VBars data={supplierBars} valueFormat={(v) => "₹" + fmtNum(v / 1000) + "k"} color={PALETTE.purple} />
        </Panel>
      </div>

      <Panel title="Expected Arrivals" hint="open PO value by week">
        <LineChart data={arrivals} valueFormat={(v) => "₹" + fmtNum(v / 1000) + "k"} color={PALETTE.cyan} />
      </Panel>

      <div className="panel-grid">
        <Panel title="Top Shortages">
          <DataTable
            columns={[
              { key: "material_code", label: "Material", render: (v) => <span className="mono strong">{v}</span> },
              { key: "description", label: "Description" },
              { key: "net_requirement", label: "Net Req", num: true, render: (v) => fmtNum(v) },
              { key: "order_value", label: "Order Value", num: true, render: fmtMoney },
              { key: "status", label: "Status", render: (v) => <Badge value={v} /> },
            ]}
            rows={data.top_shortages}
          />
        </Panel>
        <Panel title="Data Freshness">
          <DataTable
            columns={[
              { key: "label", label: "Dump" },
              { key: "rows", label: "Rows", num: true, render: (v) => fmtNum(v) },
              { key: "loaded", label: "Loaded", render: (v) => v ? <span className="badge b-green">yes</span> : <span className="badge b-grey">no</span> },
              { key: "last_ingested", label: "Last Ingested", render: (v) => v ? new Date(v).toLocaleDateString() : "—" },
            ]}
            rows={data.data_status}
          />
        </Panel>
      </div>
    </div>
  );
}
