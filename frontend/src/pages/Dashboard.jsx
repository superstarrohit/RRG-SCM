import React from "react";
import { api } from "../api/client.js";
import {
  KpiCard,
  Panel,
  BarChart,
  DataTable,
  Badge,
  Loading,
  ErrorState,
  useApi,
  fmtMoney,
  fmtNum,
} from "../components/ui.jsx";

export default function Dashboard() {
  const { loading, data, error } = useApi(() => api.overview(), []);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const k = data.kpis;
  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Overall SCM Dashboard</h1>
          <p>Executive summary across inventory, incoming, planning and sourcing · as of {data.as_of}</p>
        </div>
      </div>

      <div className="kpi-grid">
        <KpiCard label="Inventory Value" value={fmtMoney(k.inventory_value)} />
        <KpiCard label="Incoming Value" value={fmtMoney(k.incoming_value)} />
        <KpiCard
          label="Overdue Incoming"
          value={fmtMoney(k.overdue_value)}
          accent={k.overdue_value > 0 ? "red" : "green"}
        />
        <KpiCard label="Shortage Items" value={fmtNum(k.shortage_items)} accent={k.shortage_items ? "amber" : "green"} />
        <KpiCard label="Reorder Alerts" value={fmtNum(k.reorder_alerts)} accent={k.reorder_alerts ? "amber" : "green"} />
        <KpiCard label="Active Suppliers" value={fmtNum(k.active_suppliers)} />
        <KpiCard label="Single-Source Items" value={fmtNum(k.single_source_materials)} accent={k.single_source_materials ? "amber" : "green"} />
        <KpiCard label="Avg On-Time %" value={`${fmtNum(k.avg_on_time_pct, 1)}%`} />
      </div>

      <div className="panel-grid">
        <Panel title="Incoming Pipeline by Status">
          <BarChart
            data={(data.incoming_status || []).map((s) => ({
              label: s.label,
              value: s.value,
            }))}
            valueFormat={fmtMoney}
          />
        </Panel>
        <Panel title="Expected Arrivals (value / week)">
          <BarChart
            data={(data.arrival_timeline || []).map((w) => ({
              label: w.label,
              value: w.value,
            }))}
            valueFormat={fmtMoney}
          />
        </Panel>
      </div>

      <div className="panel-grid">
        <Panel title="Top Shortages">
          <DataTable
            columns={[
              { key: "material_code", label: "Material" },
              { key: "net_requirement", label: "Net Req", num: true, render: (v) => fmtNum(v) },
              { key: "order_value", label: "Order Value", num: true, render: fmtMoney },
              { key: "status", label: "Status", render: (v) => <Badge value={v} /> },
            ]}
            rows={data.top_shortages}
          />
        </Panel>
        <Panel title="Top Suppliers by Committed Value">
          <DataTable
            columns={[
              { key: "supplier_code", label: "Supplier" },
              { key: "supplier_name", label: "Name" },
              { key: "open_value", label: "Open Value", num: true, render: fmtMoney },
            ]}
            rows={data.top_suppliers}
          />
        </Panel>
      </div>

      <Panel title="Data Freshness">
        <DataTable
          columns={[
            { key: "label", label: "Dump" },
            { key: "rows", label: "Rows", num: true, render: (v) => fmtNum(v) },
            {
              key: "loaded",
              label: "Loaded",
              render: (v) => (v ? <span className="badge ok">yes</span> : <span className="badge no_date">no</span>),
            },
            {
              key: "last_ingested",
              label: "Last Ingested",
              render: (v) => (v ? new Date(v).toLocaleString() : "—"),
            },
          ]}
          rows={data.data_status}
        />
      </Panel>
    </div>
  );
}
