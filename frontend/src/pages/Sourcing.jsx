import React from "react";
import { api } from "../api/client.js";
import {
  KpiCard, Panel, PageHeader, DataTable,
  Loading, ErrorState, EmptyState, useApi, fmtMoney, fmtNum, fmtPct,
} from "../components/ui.jsx";
import { VBars, PALETTE } from "../components/charts.jsx";
import { useFilters } from "../components/filters.jsx";

export default function Sourcing() {
  const f = useFilters();
  const { loading, data, error } = useApi(() => api.sourcing({ top_n: 25, ...f.params }), [f.key]);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const head = (
    <PageHeader
      title="Sourcing Analysis"
      subtitle="Supplier spend, on-time delivery (OTIF), price benchmarking and single-source risk."
      asOf={data.as_of}
    />
  );
  if (data.empty) return <div>{head}<EmptyState message={data.message} /></div>;

  const k = data.kpis;
  const spendBars = data.supplier_spend.map((s) => ({
    label: (s.supplier_name || s.supplier_code || "").split(" ")[0], value: s.open_value,
  }));

  return (
    <div>
      {head}
      <div className="kpi-grid">
        <KpiCard label="Active Suppliers" value={fmtNum(k.active_suppliers)} icon="handshake" tone="purple" />
        <KpiCard label="Committed Value" value={fmtMoney(k.total_committed_value)} icon="dollar" tone="blue" />
        <KpiCard label="Single-Source Materials" value={fmtNum(k.single_source_materials)} icon="alert" tone="amber" />
        <KpiCard label="Avg On-Time" value={fmtPct(k.avg_on_time_pct)} icon="chart" tone="green" />
      </div>

      <div className="panel-grid">
        <Panel title="Supplier Spend" hint="open committed value">
          <VBars data={spendBars} valueFormat={(v) => "$" + fmtNum(v / 1000) + "k"} color={PALETTE.purple} />
        </Panel>
        <Panel title="On-Time Delivery (OTIF)">
          <DataTable
            columns={[
              { key: "supplier_code", label: "Supplier", render: (v) => <span className="mono">{v}</span> },
              { key: "deliveries", label: "Deliveries", num: true },
              { key: "on_time", label: "On Time", num: true },
              { key: "on_time_pct", label: "OTIF %", num: true, render: (v) => <span className={`badge ${v >= 95 ? "b-green" : v >= 80 ? "b-amber" : "b-red"}`}>{fmtPct(v)}</span> },
            ]}
            rows={data.on_time_performance}
          />
        </Panel>
      </div>

      <div className="panel-grid">
        <Panel title="Price Benchmark" hint="multi-source only">
          <DataTable
            columns={[
              { key: "material_code", label: "Material", render: (v) => <span className="mono strong">{v}</span> },
              { key: "suppliers", label: "Suppliers", num: true },
              { key: "min_price", label: "Min", num: true, render: fmtMoney },
              { key: "max_price", label: "Max", num: true, render: fmtMoney },
              { key: "spread_pct", label: "Spread", num: true, render: (v) => <span className={`badge ${v > 10 ? "b-amber" : "b-grey"}`}>{fmtPct(v)}</span> },
            ]}
            rows={data.price_benchmark}
          />
        </Panel>
        <Panel title="Single-Source Risk">
          <DataTable
            columns={[
              { key: "material_code", label: "Material", render: (v) => <span className="mono strong">{v}</span> },
              { key: "supplier_code", label: "Sole Supplier", render: (v) => <span className="mono">{v}</span> },
              { key: "supplier_name", label: "Name" },
            ]}
            rows={data.single_source_risk}
          />
        </Panel>
      </div>
    </div>
  );
}
