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
  EmptyState,
  useApi,
  fmtMoney,
  fmtNum,
} from "../components/ui.jsx";

export default function Incoming() {
  const [horizon, setHorizon] = React.useState(8);
  const { loading, data, error } = useApi(
    () => api.incoming({ horizon_weeks: horizon, top_n: 15 }),
    [horizon]
  );

  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;
  if (data.empty)
    return (
      <div>
        <Header />
        <EmptyState message={data.message} />
      </div>
    );

  const k = data.kpis;
  return (
    <div>
      <Header
        asOf={data.as_of}
        right={
          <div className="controls">
            <label>Horizon</label>
            <select value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}>
              {[4, 8, 12, 16, 26].map((w) => (
                <option key={w} value={w}>
                  {w} weeks
                </option>
              ))}
            </select>
          </div>
        }
      />

      <div className="kpi-grid">
        <KpiCard label="Open PO Lines" value={fmtNum(k.open_lines)} sub={`${fmtNum(k.materials)} materials · ${fmtNum(k.suppliers)} suppliers`} />
        <KpiCard label="Open Value" value={fmtMoney(k.open_value)} sub={`${fmtNum(k.open_qty)} units`} />
        <KpiCard label="Overdue" value={fmtMoney(k.overdue_value)} sub={`${fmtNum(k.overdue_lines)} lines · ${fmtNum(k.overdue_pct_value, 1)}% of value`} accent={k.overdue_value > 0 ? "red" : "green"} />
        <KpiCard label="Arriving ≤7d" value={fmtMoney(k.arriving_7d_value)} accent="amber" />
        <KpiCard label="Arriving ≤30d" value={fmtMoney(k.arriving_30d_value)} />
        <KpiCard label="Avg Days to Arrival" value={fmtNum(k.avg_days_to_arrival, 1)} />
      </div>

      <div className="panel-grid">
        <Panel title="Pipeline by Status">
          <BarChart
            data={data.status_breakdown.map((s) => ({ label: s.label, value: s.value }))}
            valueFormat={fmtMoney}
          />
        </Panel>
        <Panel title="Expected Arrivals Timeline (value)">
          <BarChart
            data={data.arrival_timeline.map((w) => ({ label: w.label, value: w.value }))}
            valueFormat={fmtMoney}
          />
        </Panel>
      </div>

      <Panel title="⚠ Overdue PO Lines">
        <DataTable
          columns={[
            { key: "po_number", label: "PO", render: (v, r) => `${v}${r.po_line ? "/" + r.po_line : ""}` },
            { key: "material_code", label: "Material" },
            { key: "description", label: "Description" },
            { key: "supplier_name", label: "Supplier", render: (v, r) => v || r.supplier_code },
            { key: "open_qty", label: "Open Qty", num: true, render: (v) => fmtNum(v) },
            { key: "open_value", label: "Value", num: true, render: fmtMoney },
            { key: "expected_date", label: "ETA" },
            { key: "days_overdue", label: "Days Late", num: true, render: (v) => <span className="badge overdue">{v}</span> },
          ]}
          rows={data.overdue_lines}
        />
      </Panel>

      <div className="panel-grid">
        <Panel title="Incoming by Supplier">
          <DataTable
            columns={[
              { key: "supplier_name", label: "Supplier", render: (v, r) => v || r.supplier_code },
              { key: "lines", label: "Lines", num: true },
              { key: "open_value", label: "Open Value", num: true, render: fmtMoney },
              { key: "overdue_value", label: "Overdue", num: true, render: fmtMoney },
            ]}
            rows={data.by_supplier}
          />
        </Panel>
        <Panel title="Incoming by Category">
          <DataTable
            columns={[
              { key: "category", label: "Category" },
              { key: "lines", label: "Lines", num: true },
              { key: "open_qty", label: "Qty", num: true, render: (v) => fmtNum(v) },
              { key: "open_value", label: "Value", num: true, render: fmtMoney },
            ]}
            rows={data.by_category}
          />
        </Panel>
      </div>

      <div className="panel-grid">
        <Panel title="ABC of Incoming Value">
          <DataTable
            columns={[
              { key: "abc", label: "Class", render: (v) => <Badge value={v} /> },
              { key: "materials", label: "Materials", num: true },
              { key: "open_value", label: "Value", num: true, render: fmtMoney },
              { key: "value_pct", label: "% Value", num: true, render: (v) => `${fmtNum(v, 1)}%` },
            ]}
            rows={data.abc_incoming}
          />
        </Panel>
        <Panel title="Incoming vs Current Stock (coverage)">
          <DataTable
            columns={[
              { key: "material_code", label: "Material" },
              { key: "on_hand", label: "On Hand", num: true, render: (v) => fmtNum(v) },
              { key: "incoming_qty", label: "Incoming", num: true, render: (v) => fmtNum(v) },
              { key: "total_available", label: "Total Avail", num: true, render: (v) => fmtNum(v) },
              {
                key: "incoming_vs_stock_pct",
                label: "Inc/Stock %",
                num: true,
                render: (v) => (v === null ? "no stock" : `${fmtNum(v, 0)}%`),
              },
            ]}
            rows={data.coverage}
          />
        </Panel>
      </div>
    </div>
  );
}

function Header({ asOf, right }) {
  return (
    <div className="page-header">
      <div>
        <h1>Incoming Materials Analysis</h1>
        <p>Open POs, arrivals timeline, delays, supplier & ABC breakdown{asOf ? ` · as of ${asOf}` : ""}</p>
      </div>
      {right}
    </div>
  );
}
