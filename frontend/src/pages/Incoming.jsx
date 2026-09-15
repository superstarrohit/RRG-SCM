import React from "react";
import { api } from "../api/client.js";
import {
  KpiCard, Panel, PageHeader, DataTable, Badge,
  Loading, ErrorState, EmptyState, useApi, fmtMoney, fmtNum, fmtPct,
} from "../components/ui.jsx";
import { Donut, VBars, LineChart, StatusBars, PALETTE } from "../components/charts.jsx";

const STATUS_COLOR = {
  Overdue: PALETTE.red,
  "Due this week": PALETTE.amber,
  "Due this month": PALETTE.blue,
  "Future (>30d)": PALETTE.green,
  "No ETA": PALETTE.grey,
};

export default function Incoming() {
  const { loading, data, error } = useApi(() => api.incoming({ horizon_weeks: 8, top_n: 15 }), []);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const head = (
    <PageHeader
      title="Incoming Materials Analysis"
      subtitle="Open-PO pipeline, arrivals timeline, delays, supplier & ABC breakdown, and stock coverage — the flagship module."
      asOf={data.as_of}
    />
  );
  if (data.empty) return <div>{head}<EmptyState message={data.message} /></div>;

  const k = data.kpis;
  const segs = data.status_breakdown.map((s) => ({
    label: s.label, value: s.value, color: STATUS_COLOR[s.label] || PALETTE.purple,
  }));
  const supplierBars = data.by_supplier.map((s) => ({
    label: (s.supplier_name || s.supplier_code || "").split(" ")[0], value: s.open_value,
  }));
  const arrivals = data.arrival_timeline.map((w) => ({
    label: w.label.length > 7 ? w.label.slice(5) : w.label, value: w.value,
  }));

  return (
    <div>
      {head}
      <div className="kpi-grid">
        <KpiCard label="Open PO Lines" value={fmtNum(k.open_lines)} sub={`${fmtNum(k.materials)} materials · ${fmtNum(k.suppliers)} suppliers`} icon="clipboard" tone="blue" />
        <KpiCard label="Open Value" value={fmtMoney(k.open_value)} sub={`${fmtNum(k.open_qty)} units`} icon="truck" tone="purple" />
        <KpiCard label="Overdue" value={fmtMoney(k.overdue_value)} sub={`${fmtNum(k.overdue_lines)} lines`} icon="alert" tone="red"
          delta={{ value: `${fmtPct(k.overdue_pct_value)} of value`, dir: "down" }} />
        <KpiCard label="Arriving ≤ 7d" value={fmtMoney(k.arriving_7d_value)} icon="clock" tone="amber" />
        <KpiCard label="Arriving ≤ 30d" value={fmtMoney(k.arriving_30d_value)} icon="clock" tone="cyan" />
        <KpiCard label="Avg Days to Arrival" value={fmtNum(k.avg_days_to_arrival, 1)} icon="chart" tone="green" />
      </div>

      <div className="panel-grid">
        <Panel title="Pipeline by Status">
          <Donut segments={segs} centerValue={fmtMoney(k.open_value)} centerLabel="open value" />
          <div style={{ marginTop: 16 }}>
            <StatusBars rows={segs} valueFormat={fmtMoney} />
          </div>
        </Panel>
        <Panel title="Expected Arrivals Timeline" hint="value / week">
          <LineChart data={arrivals} valueFormat={(v) => "$" + fmtNum(v / 1000) + "k"} color={PALETTE.cyan} />
        </Panel>
      </div>

      <Panel title="⚠ Overdue PO Lines">
        <DataTable
          columns={[
            { key: "po_number", label: "PO", render: (v, r) => <span className="mono">{v}{r.po_line ? "/" + r.po_line : ""}</span> },
            { key: "material_code", label: "Material", render: (v) => <span className="mono strong">{v}</span> },
            { key: "description", label: "Description" },
            { key: "supplier_name", label: "Supplier", render: (v, r) => v || r.supplier_code },
            { key: "open_qty", label: "Open Qty", num: true, render: (v) => fmtNum(v) },
            { key: "open_value", label: "Value", num: true, render: fmtMoney },
            { key: "expected_date", label: "ETA", render: (v) => <span className="mono">{v}</span> },
            { key: "days_overdue", label: "Days Late", num: true, render: (v) => <span className="badge b-red">{v}</span> },
          ]}
          rows={data.overdue_lines}
        />
      </Panel>

      <div className="panel-grid">
        <Panel title="Incoming by Supplier">
          <VBars data={supplierBars} valueFormat={(v) => "$" + fmtNum(v / 1000) + "k"} color={PALETTE.purple} />
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
              { key: "value_pct", label: "% Value", num: true, render: (v) => fmtPct(v) },
            ]}
            rows={data.abc_incoming}
          />
        </Panel>
        <Panel title="Incoming vs Current Stock" hint="coverage">
          <DataTable
            columns={[
              { key: "material_code", label: "Material", render: (v) => <span className="mono strong">{v}</span> },
              { key: "on_hand", label: "On Hand", num: true, render: (v) => fmtNum(v) },
              { key: "incoming_qty", label: "Incoming", num: true, render: (v) => fmtNum(v) },
              { key: "total_available", label: "Total Avail", num: true, render: (v) => fmtNum(v) },
              { key: "incoming_vs_stock_pct", label: "Inc/Stock", num: true, render: (v) => v == null ? "no stock" : fmtPct(v, 0) },
            ]}
            rows={data.coverage}
          />
        </Panel>
      </div>
    </div>
  );
}
